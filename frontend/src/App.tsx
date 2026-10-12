import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "./components/AppLayout";
import { KitchenPage } from "./pages/KitchenPage";
import { MorePage } from "./pages/MorePage";
import { PlaceholderPage } from "./pages/PlaceholderPage";

export function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Navigate to="/cook" replace />} />
        <Route path="/cook" element={<PlaceholderPage title="Cook" />} />
        <Route path="/buy" element={<PlaceholderPage title="Buy" />} />
        <Route path="/more" element={<MorePage />} />
        <Route path="/more/kitchen" element={<KitchenPage />} />
      </Route>
      <Route path="/onboarding" element={<PlaceholderPage title="Welcome" />} />
    </Routes>
  );
}
