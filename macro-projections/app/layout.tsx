import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Projeções Macro — Real Investor",
  description: "Tabela de projeções macroeconômicas do Brasil — Real Investor Asset Management",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body className="antialiased">{children}</body>
    </html>
  );
}
