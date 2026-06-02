import { NextResponse } from "next/server";

import { adminHeaders, backendAdminUrl } from "@/lib/admin-proxy";

export async function GET() {
  const response = await fetch(backendAdminUrl("/admin/closing-line-tracking"), {
    headers: adminHeaders(),
    cache: "no-store",
  });
  const payload = await response.json();
  return NextResponse.json(payload, { status: response.status });
}
