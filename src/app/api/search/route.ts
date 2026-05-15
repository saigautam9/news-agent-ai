import { NextResponse } from "next/server";
import { fetchStories } from "@/lib/pipeline";
import { errMessage } from "@/lib/gemini";

export const runtime = "nodejs";
export const maxDuration = 60;
export const dynamic = "force-dynamic";

// POST /api/search { query } — top angles on a topic.
export async function POST(req: Request) {
  try {
    const body = (await req.json().catch(() => ({}))) as { query?: unknown };
    const query = typeof body.query === "string" ? body.query.trim() : "";
    if (!query) {
      return NextResponse.json(
        { error: "Please provide a topic to search for." },
        { status: 400 },
      );
    }
    const data = await fetchStories(query);
    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json({ error: errMessage(e) }, { status: 500 });
  }
}
