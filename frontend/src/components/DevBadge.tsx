function DevBadge() {
  if (import.meta.env.DEV) {
    return (
      <div className="fixed right-2 top-2 rounded bg-blue-500 px-2 py-1 text-xs font-bold text-white">
        DEV | Mock Data
      </div>
    );
  }
  return null;
}

export default DevBadge;
