export default function LoadingSpinner({ size = "md" }: { size?: "sm" | "md" | "lg" }) {
  const s = size === "sm" ? "w-4 h-4" : size === "lg" ? "w-12 h-12" : "w-8 h-8";
  return (
    <div className={`${s} border-2 border-blue-600 border-t-transparent rounded-full animate-spin`} />
  );
}
