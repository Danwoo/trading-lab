import { Suspense } from "react";
import { SignupInfo } from "@/components/features/Common/Auth/Signupinfo";

export default function Page() {
  return (
    <Suspense>
      <SignupInfo />
    </Suspense>
  );
}
