import { MonitoringPanel } from './components/MonitoringPanel'
import type { FC } from 'react'

const App: FC = () => {
  return (
    <div className="min-h-screen bg-gray-100">
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
          <h1 className="text-3xl font-bold text-gray-900">
            Crypto Trading Monitor
          </h1>
        </div>
      </header>
      <main>
        <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
          <MonitoringPanel />
        </div>
      </main>
    </div>
  )
}

export default App
