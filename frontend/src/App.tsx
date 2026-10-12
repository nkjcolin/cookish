import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "./components/AppLayout";
import { KitchenPage } from "./pages/KitchenPage";
import { PlaceholderPage } from "./pages/PlaceholderPage";

export function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Navigate to="/kitchen" replace />} />
        <Route path="/kitchen" element={<KitchenPage />} />
        <Route path="/cook" element={<PlaceholderPage title="Cook" />} />
        <Route path="/shop" element={<PlaceholderPage title="Shop" />} />
        <Route path="/activity" element={<PlaceholderPage title="Activity" />} />
      </Route>
      <Route path="/onboarding" element={<PlaceholderPage title="Welcome" />} />
    </Routes>
  );
}
