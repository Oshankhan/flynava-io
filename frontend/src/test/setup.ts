import "@testing-library/jest-dom/vitest";

// jsdom lacks ResizeObserver, which Recharts' ResponsiveContainer needs.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = globalThis.ResizeObserver ?? (ResizeObserverStub as never);

// jsdom lacks matchMedia, which Ant Design's responsive observer needs.
if (!window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as never;
}

// antd v5 warns about React 18 compat in some setups; silence noisy warning.
if (!window.getComputedStyle) {
  // jsdom provides it, but guard just in case.
}
