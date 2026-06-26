import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import ContentPage from './components/ContentPage'
import './App.css'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="*" element={<ContentPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
