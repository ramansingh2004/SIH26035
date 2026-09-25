"use client";

import { useParams } from "next/navigation";

import { ReviewCase } from "@/components/review/review-case";

export default function TechnicalReviewCasePage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  return <ReviewCase sessionId={sessionId} mode="technical" />;
}
