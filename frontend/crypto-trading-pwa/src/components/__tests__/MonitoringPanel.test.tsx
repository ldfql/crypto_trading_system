import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import { MonitoringPanel } from '../MonitoringPanel'

// Mock WebSocket service
const mockAddMessageHandler = vi.fn()
const mockConnect = vi.fn()
const mockDisconnect = vi.fn()
const mockRemoveMessageHandler = vi.fn()

vi.mock('../../services/websocket', () => ({
  createWebSocketService: () => ({
    connect: mockConnect,
    disconnect: mockDisconnect,
    addMessageHandler: mockAddMessageHandler,
    removeMessageHandler: mockRemoveMessageHandler
  })
}))

describe('MonitoringPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders system metrics when received from WebSocket', async () => {
    const mockMetrics = {
      overall_accuracy: 87.00,
      total_signals: 100,
      successful_predictions: 87,
      average_confidence: 92.00,
      market_sentiment: 'bullish' as const
    }

    render(<MonitoringPanel />)

    // Verify WebSocket setup
    expect(mockConnect).toHaveBeenCalled()
    expect(mockAddMessageHandler).toHaveBeenCalled()

    // Get the message handler and simulate message
    const messageHandler = mockAddMessageHandler.mock.calls[0][0]
    await act(async () => messageHandler({ type: 'metrics_update', data: mockMetrics }))

    await waitFor(() => {
      expect(screen.getByText('System Metrics')).toBeInTheDocument()
      expect(screen.getByText('87.00%')).toBeInTheDocument()
      expect(screen.getByText('92.00%')).toBeInTheDocument()
      expect(screen.getByText('100')).toBeInTheDocument()
      expect(screen.getByText('87')).toBeInTheDocument()
      expect(screen.getByText('BULLISH')).toBeInTheDocument()
    })
  })

  it('renders trading signals when received from WebSocket', async () => {
    const mockSignal = {
      id: 1,
      symbol: 'BTC/USDT',
      signal_type: 'long' as const,
      entry_price: 45000.00,
      current_price: 46000.00,
      target_price: 47000.00,
      stop_loss: 44000.00,
      accuracy: 89.00,
      confidence: 95.00,
      market_phase: 'accumulation',
      created_at: '2024-01-17T12:00:00Z',
      validation_count: 5
    }

    render(<MonitoringPanel />)

    // Verify WebSocket setup
    expect(mockConnect).toHaveBeenCalled()
    expect(mockAddMessageHandler).toHaveBeenCalled()

    // Get the message handler and simulate message
    const messageHandler = mockAddMessageHandler.mock.calls[0][0]
    await act(async () => messageHandler({ type: 'signal_update', data: mockSignal }))

    await waitFor(() => {
      expect(screen.getByText('BTC/USDT')).toBeInTheDocument()
      expect(screen.getByText('LONG', { exact: false })).toBeInTheDocument()
      expect(screen.getByText('$45,000.00')).toBeInTheDocument()
      expect(screen.getByText('$46,000.00')).toBeInTheDocument()
      expect(screen.getByText('89.00%')).toBeInTheDocument()
      expect(screen.getByText('95.00%')).toBeInTheDocument()
      expect(screen.getByText('accumulation')).toBeInTheDocument()
      expect(screen.getByText('Validations: 5')).toBeInTheDocument()
    })
  })

  it('updates existing signal when receiving update for same ID', async () => {
    const mockSignal1 = {
      id: 1,
      symbol: 'BTC/USDT',
      signal_type: 'long' as const,
      entry_price: 45000.00,
      current_price: 46000.00,
      target_price: 47000.00,
      stop_loss: 44000.00,
      accuracy: 89.00,
      confidence: 95.00,
      market_phase: 'accumulation',
      created_at: '2024-01-17T12:00:00Z',
      validation_count: 5
    }

    const mockSignal2 = {
      ...mockSignal1,
      current_price: 47000.00,
      accuracy: 91.00,
      validation_count: 6
    }

    render(<MonitoringPanel />)

    // Verify WebSocket setup
    expect(mockConnect).toHaveBeenCalled()
    expect(mockAddMessageHandler).toHaveBeenCalled()

    // Get the message handler and simulate messages
    const messageHandler = mockAddMessageHandler.mock.calls[0][0]
    await act(async () => {
      messageHandler({ type: 'signal_update', data: mockSignal1 })
      messageHandler({ type: 'signal_update', data: mockSignal2 })
    })

    await waitFor(() => {
      expect(screen.getByText('$47,000.00')).toBeInTheDocument()
      expect(screen.getByText('91.00%')).toBeInTheDocument()
      expect(screen.getByText('Validations: 6')).toBeInTheDocument()
    })

    // Verify cleanup
    expect(mockRemoveMessageHandler).not.toHaveBeenCalled()
  })
})
