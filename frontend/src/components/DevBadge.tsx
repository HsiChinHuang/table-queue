/**
 * DEV-only badge (F-15 locks the text `DEV | Mock Data` - see DevBadge.test.tsx).
 *
 * Positioning fix: this used to be `fixed right-2 top-2` - a top-right overlay
 * sitting directly on the staff header's nav cluster (Waitlist / Tables /
 * Settings / LogOut), swallowing their clicks. The F-15 tests pin the TEXT, not
 * the placement, so it now renders bottom-left and `pointer-events-none`:
 * visible in dev, physically incapable of intercepting a click anywhere.
 */
function DevBadge() {
  if (import.meta.env.DEV) {
    return (
      <div className="pointer-events-none fixed bottom-2 left-2 rounded bg-blue-500 px-2 py-1 text-xs font-bold text-white opacity-70">
        DEV | Mock Data
      </div>
    );
  }
  return null;
}

export default DevBadge;
