import { BrowserRouter, Routes, Route } from 'react-router-dom'
import HtmlPage from './components/HtmlPage'
import './App.css'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="*" element={<HtmlPage />} />
      </Routes>
    </BrowserRouter>
  )
}