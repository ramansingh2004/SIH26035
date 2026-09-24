"""Scoped SQL access; services own permissions and transaction boundaries."""

from sqlalchemy import case, func, or_, select

from app.models.master_data import Instrument, InstrumentRange, Manufacturer
from app.models.report import Report
from app.models.testing import TestRun, TestSession


class MasterRepository:
    def __init__(self, session):
        self.session = session

    def add(self, row):
        self.session.add(row)

    async def flush(self):
        await self.session.flush()

    async def root(self, model, identifier, labs, *, lock=False):
        query = select(model).where(model.id == identifier, model.laboratory_id.in_(labs))
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        return await self.session.scalar(query)

    async def listing(self, model, labs, page, size, filters):
        query = select(model).where(model.laboratory_id.in_(labs))
        for key in (
            "laboratory_id",
            "manufacturer_id",
            "accuracy_class",
            "instrument_status",
            "registration_no",
            "country",
            "is_active",
        ):
            value = filters.get(key)
            if value is not None:
                query = query.where(getattr(model, key) == value)
        search = filters.get("search")
        if search:
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            columns = (
                [Manufacturer.name, Manufacturer.registration_no]
                if model is Manufacturer
                else [Instrument.model_name, Instrument.serial_number, Instrument.type_designation]
            )
            query = query.where(
                or_(*(column.ilike(f"%{escaped}%", escape="\\") for column in columns))
            )
        total = await self.session.scalar(select(func.count()).select_from(query.subquery()))
        column = Manufacturer.name if model is Manufacturer else Instrument.model_name
        rows = (
            await self.session.scalars(
                query.order_by(column, model.id).offset((page - 1) * size).limit(size)
            )
        ).all()
        return rows, total

    async def children(self, model, instrument_id, *, include_archived=False):
        query = select(model).where(model.instrument_id == instrument_id)
        if not include_archived:
            query = query.where(model.is_active.is_(True))
        order = model.range_no if model is InstrumentRange else model.created_at
        return (await self.session.scalars(query.order_by(order, model.id))).all()

    async def child(self, model, identifier, instrument_id, *, lock=False):
        query = select(model).where(model.id == identifier, model.instrument_id == instrument_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        return await self.session.scalar(query)

    async def instrument_history(self, instrument_id, page, size):
        run_counts = (
            select(
                TestRun.test_session_id.label("session_id"),
                func.count(TestRun.id).label("run_count"),
                func.sum(
                    case(
                        (TestRun.retest_of_run_id.is_not(None), 1),
                        else_=0,
                    )
                ).label("retest_count"),
            )
            .group_by(TestRun.test_session_id)
            .subquery()
        )

        query = (
            select(
                TestSession,
                Report,
                func.coalesce(run_counts.c.run_count, 0),
                func.coalesce(run_counts.c.retest_count, 0),
            )
            .outerjoin(
                Report,
                Report.test_session_id == TestSession.id,
            )
            .outerjoin(
                run_counts,
                run_counts.c.session_id == TestSession.id,
            )
            .where(TestSession.instrument_id == instrument_id)
        )

        total = await self.session.scalar(
            select(func.count()).select_from(
                select(TestSession.id).where(TestSession.instrument_id == instrument_id).subquery()
            )
        )
        rows = (
            await self.session.execute(
                query.order_by(
                    TestSession.session_revision_no.desc(),
                    TestSession.created_at.desc(),
                    TestSession.id,
                )
                .offset((page - 1) * size)
                .limit(size)
            )
        ).all()
        return rows, total
