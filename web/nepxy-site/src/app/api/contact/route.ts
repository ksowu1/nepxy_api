import { NextResponse } from "next/server";

export async function POST(request: Request) {
  let payload: { name?: string; email?: string; message?: string };

  try {
    payload = await request.json();
  } catch (error) {
    return NextResponse.json(
      { error: "Invalid JSON payload." },
      { status: 400 },
    );
  }

  const name = typeof payload.name === "string" ? payload.name.trim() : "";
  const email = typeof payload.email === "string" ? payload.email.trim() : "";
  const message =
    typeof payload.message === "string" ? payload.message.trim() : "";

  if (!name || !email || !message) {
    return NextResponse.json(
      { error: "Name, email, and message are required." },
      { status: 400 },
    );
  }

  console.log("NepXy contact form submission", {
    name,
    email,
    message,
  });

  return NextResponse.json({ ok: true });
}
