// components/shared/Layout/TableRow.tsx
import { ReactNode } from "react";
import { useTableGroupMode } from "./TableGroup";

interface Props {
  children: ReactNode;
  verticalAlign?: "top" | "middle" | "bottom";
  className?: string;
}

export function TableRow({ children, verticalAlign = "middle", className = "" }: Props) {
  const mode = useTableGroupMode();

  if (mode === "flex") {
    const alignClass =
      verticalAlign === "top" ? "items-start" : verticalAlign === "bottom" ? "items-end" : "items-stretch";
    return <div className={`flex flex-1 min-h-0 ${alignClass} ${className}`}>{children}</div>;
  }

  return (
    <tr className={className} style={{ verticalAlign }}>
      {children}
    </tr>
  );
}
