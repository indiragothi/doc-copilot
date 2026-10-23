import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"

import { AuthProvider } from "@/components/auth-provider"
import { ProtectedRoute } from "@/components/protected-route"
import ChatHomePage from "@/pages/chat-home"
import ChatLayout from "@/pages/chat-layout"
import ChatThreadPage from "@/pages/chat-thread"
import SignInPage from "@/pages/sign-in"
import SignUpPage from "@/pages/sign-up"

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<SignInPage />} />
          <Route path="/signup" element={<SignUpPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<ChatLayout />}>
              <Route path="/chat" element={<ChatHomePage />} />
              <Route path="/chat/:threadId" element={<ChatThreadPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/chat" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
