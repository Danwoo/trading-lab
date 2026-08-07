"use client";

import "@/styles/globals.css";
import { MessagePopup, ToastNotification } from "@/components/shared/Feedback";
import { env } from "@/env";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <head>
        <title>{env.NEXT_PUBLIC_APP_NAME}</title>
        <meta property="og:type" content="website" />
        <meta property="og:title" content={env.NEXT_PUBLIC_APP_NAME} />
        <link rel="icon" href="/favicon.ico" />
      </head>
      <body className="font-Pretendard">
        {children}
        <MessagePopup />
        <ToastNotification />
      </body>
    </html>
  );
}
