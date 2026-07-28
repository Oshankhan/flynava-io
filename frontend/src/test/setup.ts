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

// jsdom doesn't implement scrollIntoView at all (InayaChat scrolls its
// message list on every new turn).
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}

// jsdom's selector engine (nwsapi) rejects a couple of the selectors antd v5's
// CSS-in-JS emits — e.g. `*+.ant-select-item-option-selected:not(…))`, which it
// reports as "not a valid selector". Any DOM read that happens to walk those
// rules (antd's Table does, once a Select's styles are in the document) then
// throws a SyntaxError straight through React's commit phase and fails the
// test for a reason that has nothing to do with the component.
//
// Browsers parse these fine, so treat an unparseable selector as "matches
// nothing" rather than an error. Only SyntaxError is swallowed; every other
// failure still propagates.
function tolerateUnparseableSelectors() {
  const originalMatches = Element.prototype.matches;
  Element.prototype.matches = function (this: Element, selector: string) {
    try {
      return originalMatches.call(this, selector);
    } catch (err) {
      if (err instanceof DOMException && err.name === "SyntaxError") return false;
      throw err;
    }
  };

  const originalQuerySelectorAll = Element.prototype.querySelectorAll;
  Element.prototype.querySelectorAll = function (this: Element, selector: string) {
    try {
      return originalQuerySelectorAll.call(this, selector);
    } catch (err) {
      if (err instanceof DOMException && err.name === "SyntaxError")
        return document.createDocumentFragment().querySelectorAll("*");
      throw err;
    }
  } as typeof Element.prototype.querySelectorAll;
}

tolerateUnparseableSelectors();

// jsdom throws "Not implemented" for the two-argument form of
// getComputedStyle. rc-table calls it that way to measure the scrollbar
// whenever a table has horizontal scroll, and the resulting unhandled error
// intermittently fails the whole test file. Drop the pseudo-element argument —
// jsdom wouldn't compute pseudo-element styles anyway.
const originalGetComputedStyle = window.getComputedStyle.bind(window);
window.getComputedStyle = ((element: Element) =>
  originalGetComputedStyle(element)) as typeof window.getComputedStyle;
