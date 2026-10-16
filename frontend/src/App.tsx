import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "./components/AppLayout";
import { AddIngredientsPage } from "./pages/AddIngredientsPage";
import { BuyPage } from "./pages/BuyPage";
import { ConfirmPurchasePage } from "./pages/ConfirmPurchasePage";
import { CookPage } from "./pages/CookPage";
import { HistoryPage } from "./pages/HistoryPage";
import { KitchenPage } from "./pages/KitchenPage";
import { MorePage } from "./pages/MorePage";
import { OnboardingPage } from "./pages/OnboardingPage";
import { PreferencesPage } from "./pages/PreferencesPage";
import { RecipePage } from "./pages/RecipePage";
import { ReviewDraftPage } from "./pages/ReviewDraftPage";

export function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Navigate to="/cook" replace />} />
        <Route path="/cook" element={<CookPage />} />
        <Route path="/buy" element={<BuyPage />} />
        <Route path="/more" element={<MorePage />} />
        <Route path="/more/kitchen" element={<KitchenPage />} />
        <Route path="/more/add" element={<AddIngredientsPage />} />
        <Route path="/more/history" element={<HistoryPage />} />
      </Route>
      <Route element={<AppLayout tabBar={false} />}>
        <Route path="/buy/confirm" element={<ConfirmPurchasePage />} />
        <Route path="/cook/recipe" element={<RecipePage />} />
        <Route path="/more/add/review" element={<ReviewDraftPage />} />
        <Route path="/more/preferences" element={<PreferencesPage />} />
      </Route>
      <Route path="/onboarding" element={<OnboardingPage />} />
    </Routes>
  );
}
