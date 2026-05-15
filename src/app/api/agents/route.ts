import { NextResponse } from "next/server";
import { buildAgentTakes } from "@/lib/pipeline";
import { errMessage } from "@/lib/gemini";

export const runtime = "nodejs";
export const maxDuration = 60;
export const dynamic = "force-dynamic";

// POST /api/agents { story: { headline, summary } } — 5 analyst views + debate.
export async function POST(req: Request) {
  try {
    const body = (await req.json().catch(() => ({}))) as {
      story?: { headline?: unknown; summary?: unknown };
    };
    const headline =
      typeof body.story?.headline === "string" ? body.story.headline : "";
    const summary =
      typeof body.story?.summary === "string" ? body.story.summary : "";
    if (!headline) {
      return NextResponse.json(
        { error: "A story with a headline is required." },
        { status: 400 },
      );
    }
    const data = await buildAgentTakes({ headline, summary });
    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json({ error: errMessage(e) }, { status: 500 });
  }
}
