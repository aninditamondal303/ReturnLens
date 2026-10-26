import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { FilterProvider } from "./state/FilterContext";
import Overview from "./pages/Overview";
import RiskAnalysis from "./pages/RiskAnalysis";
import ProfitLeakage from "./pages/ProfitLeakage";
import ProductIntelligence from "./pages/ProductIntelligence";
import CustomerGeography from "./pages/CustomerGeography";
import WhatIfSimulator from "./pages/WhatIfSimulator";
import DataExplorer from "./pages/DataExplorer";

function NotFound() {
  return (
    <div className="panel p-8">
      <h2 className="text-[16px] font-semibold">This page does not exist</h2>
      <p className="mt-1 text-[13px] text-slate-ink">Use the navigation rail, or go back to the overview.</p>
      <Link to="/" className="btn mt-3">Open Executive Overview</Link>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <FilterProvider>
        <AppShell>
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/risk" element={<RiskAnalysis />} />
            <Route path="/leakage" element={<ProfitLeakage />} />
            <Route path="/products" element={<ProductIntelligence />} />
            <Route path="/geography" element={<CustomerGeography />} />
            <Route path="/simulator" element={<WhatIfSimulator />} />
            <Route path="/data" element={<DataExplorer />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </AppShell>
      </FilterProvider>
    </BrowserRouter>
  );
}
