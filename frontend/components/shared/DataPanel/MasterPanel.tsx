import { Button } from "@/components/shared/ui/Button";
import type { ActionButton } from "@/components/shared/ui";

interface Props {
  title?: React.ReactNode;
  buttons?: ActionButton[];
  children: React.ReactNode;
}

export function MasterPanel({ title, buttons = [], children }: Props) {
  return (
    <div className="h-full flex flex-col">
      <div className="flex justify-between items-center p-2">
        <h2 className="text-lg text-gray-700">📋 {title}</h2>
        {buttons.length > 0 && (
          <div className="flex gap-2">
            {buttons
              .filter((button) => button.visible !== false)
              .map((button, idx) => {
                const { visible, sort: _sort, ...buttonProps } = button;
                return <Button key={idx} width={button.width || 40} {...buttonProps} />;
              })}
          </div>
        )}
      </div>
      <div className="flex-1 min-h-0">{children}</div>
    </div>
  );
}
