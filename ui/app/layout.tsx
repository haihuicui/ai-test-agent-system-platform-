import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import { Toaster } from "sonner";
import { LanguageProvider } from "@/providers/LanguageProvider";
import "./globals.css";
// TODO  MC8yOmFIVnBZMlhsdEpUbXRiZm92b2s2UzBkNlFnPT06NzA3OTIzNzM=

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "灵犀测试平台",
  description: "AI 驱动的智能测试系统",
  icons: {
    icon: "/logo.svg",
    shortcut: "/logo.svg",
    apple: "/logo.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body className={inter.className} suppressHydrationWarning>
        <LanguageProvider>
          <NuqsAdapter>{children}</NuqsAdapter>
          <Toaster position="top-right" />
        </LanguageProvider>
      </body>
    </html>
  );
}
// eslint-disable  MS8yOmFIVnBZMlhsdEpUbXRiZm92b2s2UzBkNlFnPT06NzA3OTIzNzM=

