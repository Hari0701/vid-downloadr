import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "vid-downloadr — open-source media downloader",
  description:
    "Paste a link from YouTube, Instagram, Twitter/X, Pinterest and a thousand other sites, and download the media.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
