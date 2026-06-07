import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Voice Property Intake Agent",
  description:
    "Голосовой AI-агент для первичного интервью собственника недвижимости",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
