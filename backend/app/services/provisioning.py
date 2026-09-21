import asyncio

from app.core.errors import AppError
from app.core.security import hash_password
from app.repositories.identity import IdentityRepository
from app.repositories.provisioning import ProvisioningRepository
from app.services.audit import AuditService, RequestContext


class ProvisioningService:
    def __init__(self, session):
        self.session = session
        self.repo = ProvisioningRepository(session)
        self.audit = AuditService(IdentityRepository(session), RequestContext())

    async def seed(self):
        async with self.session.begin():
            await self.repo.lock()
            changed = await self.repo.seed()
            if changed:
                self.audit.record(
                    "system.permissions_seeded",
                    None,
                    "roles",
                    system=True,
                    reason="Specification Freeze v1",
                    after={"inserted_rows": changed},
                )
            return changed

    async def bootstrap(self, email, name, password):
        if not 12 <= len(password) <= 128:
            raise ValueError("Password must contain 12–128 characters")
        async with self.session.begin():
            await self.repo.lock()
            changed = await self.repo.seed()
            if await self.repo.has_admin():
                raise AppError(409, "ADMIN_EXISTS", "A global administrator already exists")
            user = await self.repo.create_admin(
                email, name, await asyncio.to_thread(hash_password, password)
            )
            if changed:
                self.audit.record(
                    "system.permissions_seeded",
                    None,
                    "roles",
                    system=True,
                    after={"inserted_rows": changed},
                )
            self.audit.record("system.admin_bootstrapped", user.id, "users", user.id, system=True)
            return user.id
