import { Suspense } from "react";
import { PassSearchinfo } from "@/components/features/Common/Auth/PassSearchinfo";

export default function Page() {
  return (
    <Suspense>
      <PassSearchinfo />
    </Suspense>
  );
}
