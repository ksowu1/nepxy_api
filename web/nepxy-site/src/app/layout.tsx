import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NepXy — Cross-border wallet & payouts",
  description:
    "Fast, compliant cross-border wallet and payouts from North America and Europe to West Africa.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="bg-white font-sans text-slate-900 antialiased">
        {children}
      </body>
    </html>
  );
}
