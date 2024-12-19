import '@testing-library/jest-dom'
import { vi } from 'vitest'

class MockWebSocket {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3

  url: string
  readyState: number = MockWebSocket.CONNECTING
  onopen: ((event: any) => void) | null = null
  onclose: ((event: any) => void) | null = null
  onmessage: ((event: any) => void) | null = null
  onerror: ((event: any) => void) | null = null
  private messageQueue: string[] = []

  constructor(url: string) {
    this.url = url
    // Simulate connection after a small delay
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN
      if (this.onopen) {
        this.onopen({ type: 'open' })
      }
      // Process any queued messages
      this.processMessageQueue()
    }, 0)
  }

  close() {
    this.readyState = MockWebSocket.CLOSED
    if (this.onclose) {
      this.onclose({ type: 'close' })
    }
  }

  send(data: string) {
    if (this.readyState === MockWebSocket.OPEN) {
      // Process message immediately if connection is open
      if (this.onmessage) {
        this.onmessage({ type: 'message', data })
      }
    } else {
      // Queue message if connection is not yet open
      this.messageQueue.push(data)
    }
  }

  private processMessageQueue() {
    if (this.readyState === MockWebSocket.OPEN && this.onmessage) {
      while (this.messageQueue.length > 0) {
        const data = this.messageQueue.shift()
        if (data) {
          this.onmessage({ type: 'message', data })
        }
      }
    }
  }

  addEventListener(event: string, callback: (event: any) => void) {
    switch (event) {
      case 'open':
        this.onopen = callback
        break
      case 'close':
        this.onclose = callback
        break
      case 'message':
        this.onmessage = callback
        break
      case 'error':
        this.onerror = callback
        break
    }
  }

  removeEventListener(event: string, callback: (event: any) => void) {
    switch (event) {
      case 'open':
        this.onopen = null
        break
      case 'close':
        this.onclose = null
        break
      case 'message':
        this.onmessage = null
        break
      case 'error':
        this.onerror = null
        break
    }
  }
}

// Mock WebSocket
global.WebSocket = MockWebSocket as any
