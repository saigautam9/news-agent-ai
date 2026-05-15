import { NextResponse } from "next/server";
import { fetchStories } from "@/lib/pipeline";
import { errMessage } from "@/lib/gemini";

export const runtime = "nodejs";
export const maxDuration = 60;
export const dynamic = "force-dynamic";

// GET /api/news — today's most important stories.
export async function GET() {
  try {
    const data = await fetchStories();
    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json({ error: errMessage(e) }, { status: 500 });
  }
}
