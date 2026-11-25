import type { NextConfig } from "next";

// Sent on every route. No X-Frame-Options, frame-ancestors or Content-Security-Policy
// here: the site is meant to be embedded in another page.
const securityHeaders: { key: string; value: string }[] = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

// Every page reads live numbers from the backend per request; the backend owns the
// ten-minute cache, so the frontend keeps none.
const nextConfig: NextConfig = {
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
