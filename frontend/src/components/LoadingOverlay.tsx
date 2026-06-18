import { Icon } from "./Icon";

type Props = {
  message: string;
  sub?: string;
};

export function LoadingOverlay({ message, sub }: Props) {
  return (
    <div className="loading-overlay">
      <div className="loading-overlay__card">
        <Icon name="loader" size={36} />
        <p className="loading-overlay__msg">{message}</p>
        {sub && <p className="loading-overlay__sub">{sub}</p>}
      </div>
    </div>
  );
}
