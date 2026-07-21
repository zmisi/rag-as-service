import { headers } from "next/headers";
import { redirect } from "next/navigation";

import {
  hostnameFromHostHeader,
  isApexHost,
  isTenantHost,
} from "@/lib/hosts";

export default async function HomePage() {
  const hostHeader = (await headers()).get("host") ?? "";
  const hostname = hostnameFromHostHeader(hostHeader);

  if (isApexHost(hostname)) {
    redirect("/login");
  }

  if (isTenantHost(hostname)) {
    redirect("/chat");
  }

  redirect("/login");
}
