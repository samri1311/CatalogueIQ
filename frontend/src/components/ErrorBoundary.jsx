import { Component } from "react";

// Last-resort guard so an unexpected rendering error shows a message instead of a blank page.
export default class ErrorBoundary extends Component {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div role="alert" className="mx-auto mt-16 max-w-md rounded-lg border border-red-200 bg-red-50 p-6 text-center">
        <h1 className="mb-2 text-lg font-semibold text-red-800">Something went wrong</h1>
        <p className="mb-4 text-sm text-red-700">The page hit an unexpected error. Your data on the server is unchanged.</p>
        <a href="/" className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white">Start over</a>
      </div>
    );
  }
}
