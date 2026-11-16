import type { NextConfig } from "next";

// Every page reads live numbers from the backend per request; the backend owns the
// ten-minute cache, so the frontend keeps none.
const nextConfig: NextConfig = {};

export default nextConfig;
