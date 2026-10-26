import { useState } from "react";
import { Download } from "lucide-react";
import { downloadCsv, type Query } from "../services/api";
import { int } from "../utils/format";

/** Exports the full filtered result set (not just the visible page) as CSV via the API. */
export function ExportButton({ path, params, fileName, label = "Export CSV" }: { path: string; params: Query; fileName: string; label?: string }) {
  const [state, setState] = useState<{ busy: boolean; msg: string | null; error: boolean }>({ busy: false, msg: null, error: false });
  const run = async () => {
    setState({ busy: true, msg: null, error: false });
    try {
      const n = await downloadCsv(path, params, fileName);
      setState({ busy: false, msg: `Exported ${int(n)} rows`, error: false });
    } catch (e) {
      setState({ busy: false, msg: (e as Error).message, error: true });
    }
    setTimeout(() => setState((s) => ({ ...s, msg: null })), 4000);
  };
  return (
    <span className="inline-flex items-center gap-2">
      {state.msg && (
        <span role="status" className={`text-[11.5px] ${state.error ? "text-vermilion-ink" : "text-teal"}`}>
          {state.msg}
        </span>
      )}
      <button type="button" className="btn h-7" onClick={run} disabled={state.busy}>
        <Download size={13} /> {state.busy ? "Exporting…" : label}
      </button>
    </span>
  );
}
