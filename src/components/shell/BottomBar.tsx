export interface PrimaryAction {
  label: string;
  disabled: boolean;
}

export function BottomBar({
  primary,
  onPrimary,
}: {
  primary: PrimaryAction;
  onPrimary: () => void;
}) {
  return (
    <div className="bottom-bar">
      <div className="bottom-inner">
        <button className="primary-button" type="button" disabled={primary.disabled} onClick={onPrimary}>
          {primary.label}
        </button>
      </div>
    </div>
  );
}
