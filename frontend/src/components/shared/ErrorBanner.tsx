import { AlertCircle } from "lucide-react";

export default function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-2 p-4 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-700 rounded-lg text-red-700 dark:text-red-400">
      <AlertCircle className="w-4 h-4 flex-shrink-0" />
      <p className="text-sm">{message}</p>
    </div>
  );
}
