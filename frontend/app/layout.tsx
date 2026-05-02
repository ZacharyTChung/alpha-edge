import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Alpha Edge",
  description: "Prediction market intelligence engine",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <header className="header">
          <h1>Alpha Edge</h1>
          <nav>
            <a href="/">Markets</a>
            <a href="/edge">Edge Report</a>
            <a href="/calibration">Calibration</a>
          </nav>
        </header>
        <main className="main">{children}</main>
      </body>
    </html>
  );
}
