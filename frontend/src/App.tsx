import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { useApi } from "./hooks/useApi";
import { api } from "./lib/api";
import type { Overview } from "./lib/types";
import { AuthProvider } from "./auth";

import OverviewPage from "./pages/Overview";
import NetworkMapPage from "./pages/NetworkMapPage";
import TrafficPage from "./pages/Traffic";
import ThreatsPage from "./pages/Threats";
import NewsPage from "./pages/News";
import ClaimsPage from "./pages/Claims";
import SpamPage from "./pages/Spam";
import ReportsPage from "./pages/Reports";
import SourcesPage from "./pages/Sources";
import HealthPage from "./pages/Health";
import BudgetPage from "./pages/Budget";
import SettingsPage from "./pages/Settings";

export default function App() {
  // Lightweight header feed: mode indicator + alert badge, polled gently.
  const overview = useApi<Overview>(() => api.get<Overview>("/overview"), [], {
    pollMs: 30000,
  });

  return (
    <AuthProvider>
      <Layout
        status={overview.data?.status}
        alertCount={overview.data?.kpis.active_alerts}
      >
        <Routes>
          <Route path="/" element={<OverviewPage />} />
          <Route path="/map" element={<NetworkMapPage />} />
          <Route path="/traffic" element={<TrafficPage />} />
          <Route path="/threats" element={<ThreatsPage />} />
          <Route path="/news" element={<NewsPage />} />
          <Route path="/claims" element={<ClaimsPage />} />
          <Route path="/spam" element={<SpamPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/sources" element={<SourcesPage />} />
          <Route path="/health" element={<HealthPage />} />
          <Route path="/budget" element={<BudgetPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<OverviewPage />} />
        </Routes>
      </Layout>
    </AuthProvider>
  );
}
