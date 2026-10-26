import { api } from "../services/api";
import { useApi } from "../hooks/useApi";
import { useFilters } from "../state/FilterContext";
import type { GeographyResponse, GroupRow } from "../types/api";
import { EmptyState, ErrorState, Notice, Panel, PanelSkeleton, RateBar } from "../components/ui";
import { DataTable, type Column } from "../components/DataTable";
import { RankedBars } from "../charts/charts";
import { C } from "../charts/theme";
import { inr, inrCompact, int, pct } from "../utils/format";

const TARGET = 0.08;

export default function CustomerGeography() {
  const { query, queryKey, resetFilters } = useFilters();
  const { data, error, loading, refreshing, reload } = useApi<GeographyResponse>((s) => api.geography(query, { signal: s }), queryKey);
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (loading || !data) return <div className="grid grid-cols-1 gap-4 lg:grid-cols-3"><PanelSkeleton label="regions" /><PanelSkeleton label="return rates" /><PanelSkeleton label="costs" /></div>;
  if (data.regions.length === 0) return <div className="panel"><EmptyState onReset={resetFilters} /></div>;

  const byGmv = [...data.regions].sort((a, b) => (b.gmv ?? 0) - (a.gmv ?? 0));
  const byRate = [...data.regions].sort((a, b) => (b.unit_return_rate ?? 0) - (a.unit_return_rate ?? 0));
  const byCost = [...data.regions].filter((r) => r.incremental_per_returned_order !== null).sort((a, b) => (b.incremental_per_returned_order ?? 0) - (a.incremental_per_returned_order ?? 0));
  const avgCost = data.summary.incremental_per_returned_order ?? 0;
  const maxRate = Math.max(...data.regions.map((r) => r.unit_return_rate ?? 0), ...data.segments.map((r) => r.unit_return_rate ?? 0));

  return (
    <div className={`flex flex-col gap-4 transition-opacity duration-150 ${refreshing ? "opacity-70" : ""}`}>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Panel label="Geography / sales" title="Gross merchandise value by region">
          <RankedBars rows={byGmv} labelKey="shipping_region" valueKey="gmv" format={inrCompact} colorFor={() => C.slate}
            tooltipRows={(r) => [{ label: "GMV", value: inr(r.gmv) }, { label: "Share of GMV", value: pct(r.gmv_share) }, { label: "Orders", value: int(r.eligible_orders) }]} />
        </Panel>
        <Panel label="Geography / returns" title="Unit return rate by region" subtitle={`Vermilion = above the ${pct(TARGET, 0)} example target.`}>
          <RankedBars rows={byRate} labelKey="shipping_region" valueKey="unit_return_rate" format={(v) => pct(v)} colorFor={(r) => ((r.unit_return_rate ?? 0) > TARGET ? C.vermilion : C.teal)}
            tooltipRows={(r) => [{ label: "Unit return rate", value: pct(r.unit_return_rate) }, { label: "Order return rate", value: pct(r.order_return_rate) }, { label: "Returned units", value: int(r.returned_units) }]} />
        </Panel>
        <Panel label="Geography / cost to serve returns" title="Incremental cost per returned order" subtitle={`Portfolio average ${inr(avgCost)}. Includes logistics, inspection and write-offs.`}>
          <RankedBars rows={byCost} labelKey="shipping_region" valueKey="incremental_per_returned_order" format={(v) => inrCompact(v)} colorFor={(r) => ((r.incremental_per_returned_order ?? 0) > avgCost * 1.1 ? C.vermilion : C.slate)}
            tooltipRows={(r) => [{ label: "Per returned order", value: inr(r.incremental_per_returned_order) }, { label: "Total incremental costs", value: inr(r.incremental_costs) }, { label: "Returned orders", value: int(r.returned_orders) }, { label: "Zone", value: r.shipping_zone ?? "—" }]} />
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <Panel className="xl:col-span-8" label="Regional ledger" title="Return-related costs by region" bodyClass="p-0" subtitle="Share of reverse-logistics spend against share of sales shows where returns are expensive to serve.">
          <DataTable<GroupRow>
            caption="Regional return costs"
            rows={data.regions}
            rowKey={(r) => r.shipping_region ?? ""}
            localSort
            sort={{ by: "incremental_costs", dir: "desc" }}
            dense
            columns={[
              { key: "shipping_region", header: "Region", sortable: true, render: (r) => <span className="font-medium">{r.shipping_region}</span> },
              { key: "shipping_zone", header: "Zone", sortable: true },
              { key: "gmv", header: "GMV", align: "right", sortable: true, render: (r) => inrCompact(r.gmv) },
              { key: "unit_return_rate", header: "Return rate", sortable: true, render: (r) => <RateBar value={r.unit_return_rate} max={maxRate} target={TARGET} /> },
              { key: "reverse_logistics", header: "Rev. logistics", align: "right", sortable: true, render: (r) => inrCompact(r.reverse_logistics) },
              { key: "incremental_costs", header: "Incr. costs", align: "right", sortable: true, render: (r) => <span className="text-vermilion-ink">{inrCompact(r.incremental_costs)}</span> },
              { key: "reverse_logistics_share", header: "Logistics share", align: "right", sortable: true, render: (r) => pct(r.reverse_logistics_share) },
              { key: "gmv_share", header: "Sales share", align: "right", sortable: true, render: (r) => pct(r.gmv_share) },
              {
                key: "ratio", header: "Over-index", align: "right", tip: "Logistics share ÷ sales share. Above 1.25x is highlighted.",
                render: (r) => {
                  const ratio = r.gmv_share ? (r.reverse_logistics_share ?? 0) / r.gmv_share : null;
                  return <span className={ratio !== null && ratio >= 1.25 ? "font-semibold text-vermilion-ink" : ""}>{ratio === null ? "—" : `${ratio.toFixed(2)}x`}</span>;
                },
              },
            ]}
          />
        </Panel>
        <Panel className="xl:col-span-4" label="Shipping zones" title="Reverse-logistics cost by zone" bodyClass="p-0" subtitle="Distance from the fulfilment centre drives pickup cost.">
          <table className="w-full text-[12.5px]">
            <caption className="sr-only">Reverse logistics by shipping zone</caption>
            <thead><tr>{["Zone", "Returned units", "Logistics / unit", "Return rate"].map((h, i) => <th key={h} scope="col" className={`table-head border-b border-line px-3 py-2 ${i ? "text-right" : ""}`}>{h}</th>)}</tr></thead>
            <tbody>
              {data.zones.map((z) => (
                <tr key={z.shipping_zone ?? ""} className="border-b border-line/70">
                  <td className="px-3 py-2 font-medium">{z.shipping_zone}</td>
                  <td className="num px-3 text-right">{int(z.returned_units)}</td>
                  <td className="num px-3 text-right">{inr(z.returned_units ? (z.reverse_logistics ?? 0) / ((z.returned_units ?? 0) + (z.rejected_units ?? 0)) : null)}</td>
                  <td className="num px-3 text-right">{pct(z.unit_return_rate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <Panel className="xl:col-span-7" label="Customer segments / aggregated" title="Segment performance" bodyClass="p-0" subtitle="Value per customer is a 12-month proxy — only one year of history exists, so it is not lifetime value.">
          <DataTable<GroupRow>
            caption="Customer segment performance"
            rows={data.segments}
            rowKey={(r) => r.customer_segment ?? ""}
            localSort
            sort={{ by: "gmv", dir: "desc" }}
            dense
            columns={[
              { key: "customer_segment", header: "Segment", sortable: true, render: (r) => <span className="font-medium">{r.customer_segment}</span> },
              { key: "active_customers", header: "Customers", align: "right", sortable: true, render: (r) => int(r.active_customers) },
              { key: "avg_order_value", header: "AOV", align: "right", sortable: true, render: (r) => inr(r.avg_order_value), tip: "Net merchandise sales ÷ orders." },
              { key: "orders_per_customer", header: "Orders / cust.", align: "right", sortable: true, render: (r) => (r.orders_per_customer ?? 0).toFixed(2) },
              { key: "unit_return_rate", header: "Return rate", sortable: true, render: (r) => <RateBar value={r.unit_return_rate} max={maxRate} target={TARGET} /> },
              { key: "return_leakage", header: "Return leakage", align: "right", sortable: true, render: (r) => <span className="text-vermilion-ink">{inrCompact(r.return_leakage)}</span> },
              { key: "contribution_per_customer", header: "Contrib. / cust.", align: "right", sortable: true, render: (r) => inr(r.contribution_per_customer), tip: "Estimated contribution after return costs per active customer over the selected period." },
            ]}
          />
        </Panel>
        <Panel className="xl:col-span-5" label="New vs repeat" title="First orders versus returning customers" bodyClass="p-0">
          <div className="grid grid-cols-2 divide-x divide-line">
            {data.customer_type.map((t) => (
              <div key={t.customer_type} className="p-4">
                <div className="text-[13px] font-semibold">{t.customer_type} customers</div>
                <dl className="mt-2 space-y-1.5 text-[12.5px]">
                  <div className="flex justify-between"><dt className="text-slate-ink">Orders</dt><dd className="num">{int(t.eligible_orders)}</dd></div>
                  <div className="flex justify-between"><dt className="text-slate-ink">AOV</dt><dd className="num">{inr(t.avg_order_value)}</dd></div>
                  <div className="flex justify-between"><dt className="text-slate-ink">Unit return rate</dt><dd className="num">{pct(t.unit_return_rate)}</dd></div>
                  <div className="flex justify-between"><dt className="text-slate-ink">Order return rate</dt><dd className="num">{pct(t.order_return_rate)}</dd></div>
                  <div className="flex justify-between"><dt className="text-slate-ink">Contribution margin</dt><dd className="num">{pct(t.contribution_margin)}</dd></div>
                </dl>
              </div>
            ))}
          </div>
          <div className="border-t border-line p-4">
            <div className="section-label mb-2">Return rate by prior order history</div>
            <RankedBars rows={data.history_bands} labelKey="historical_order_count_band" valueKey="unit_return_rate" format={(v) => pct(v)} labelWidth={50} height={150}
              colorFor={(r) => ((r.unit_return_rate ?? 0) > TARGET ? C.vermilion : C.teal)}
              tooltipRows={(r) => [{ label: "Prior orders", value: r.historical_order_count_band ?? "" }, { label: "Return rate", value: pct(r.unit_return_rate) }, { label: "Orders", value: int(r.eligible_orders) }]} />
          </div>
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <SmallTable title="Sales channels" label="Channel mix" rows={data.channels} labelKey="sales_channel" maxRate={maxRate} />
        <SmallTable title="Payment methods" label="Payment mix" rows={data.payments} labelKey="payment_method" maxRate={maxRate} />
      </div>

      <Notice>{data.notes.join(" ")}</Notice>
    </div>
  );
}

function SmallTable({ title, label, rows, labelKey, maxRate }: { title: string; label: string; rows: GroupRow[]; labelKey: "sales_channel" | "payment_method"; maxRate: number }) {
  const columns: Column<GroupRow>[] = [
    { key: labelKey, header: title.replace(/s$/, ""), sortable: true, render: (r) => <span className="font-medium">{r[labelKey]}</span> },
    { key: "gmv_share", header: "Sales share", align: "right", sortable: true, render: (r) => pct(r.gmv_share) },
    { key: "unit_return_rate", header: "Return rate", sortable: true, render: (r) => <RateBar value={r.unit_return_rate} max={maxRate} target={TARGET} /> },
    { key: "incremental_costs", header: "Incr. costs", align: "right", sortable: true, render: (r) => inrCompact(r.incremental_costs) },
    { key: "contribution_margin", header: "Margin", align: "right", sortable: true, render: (r) => pct(r.contribution_margin) },
  ];
  return (
    <Panel label={label} title={title} bodyClass="p-0">
      <DataTable caption={title} rows={rows} columns={columns} rowKey={(r) => String(r[labelKey])} localSort sort={{ by: "gmv_share", dir: "desc" }} dense />
    </Panel>
  );
}
