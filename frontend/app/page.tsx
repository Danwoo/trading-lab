import { Suspense } from "react";
import { Login } from "@/components/features/Common/Auth/Login";

export default function Page() {
  return (
    <Suspense>
      <Login />
    </Suspense>
  );
}
