/**
 * FarmTwin 라우터 엔트리.
 *
 * /           환경 관제
 * /records    센서 기록
 * /control    설비 제어
 * /twin       3D · 장치 제어
 * /crops      작물 생육
 */

import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import './App.css'
import { AppShell } from './layout/AppShell'
import { CropGrowthPage } from './pages/CropGrowthPage'
import { DashboardPage } from './pages/DashboardPage'
import { EquipmentControlPage } from './pages/EquipmentControlPage'
import { SensorRecordsPage } from './pages/SensorRecordsPage'
import { TwinControlPage } from './pages/TwinControlPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<DashboardPage />} />
          <Route path="records" element={<SensorRecordsPage />} />
          <Route path="control" element={<EquipmentControlPage />} />
          <Route path="events" element={<Navigate to="/control" replace />} />
          <Route path="twin" element={<TwinControlPage />} />
          <Route path="crops" element={<CropGrowthPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
