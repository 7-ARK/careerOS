import { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {LogOut} from 'lucide-react';
import {User} from '../lib/api';

export function Header({user, onLogout}: {user: User; onLogout: () => void}) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <motion.header
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      className="sticky top-0 z-50 border-b border-border/70 bg-background/86 px-4 py-3 backdrop-blur sm:px-6"
      id="app-header"
    >
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-1 py-1">
        <a href="/" className="flex items-center gap-2">
          <motion.span 
            className="text-lg font-semibold tracking-tight text-foreground"
            whileHover={{ scale: 1.02 }}
          >
            career<span className="text-primary">OS</span>
          </motion.span>
        </a>

        <div className="hidden items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground md:flex">
          <span className="size-2 rounded-full bg-primary" />
          Workspace
        </div>

        <div className="hidden items-center gap-3 md:flex">
          <span className="max-w-44 truncate text-sm text-muted-foreground">{user.full_name || user.email}</span>
          <motion.button
            type="button"
            onClick={onLogout}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className="cozy-button-secondary inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition"
          >
            <LogOut className="size-4" />Logout
          </motion.button>
        </div>

        {/* Mobile menu button */}
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="flex h-10 w-10 items-center justify-center rounded-full transition-colors hover:bg-secondary md:hidden"
          aria-label="Toggle menu"
          id="toggle-menu-btn"
        >
          <div className="flex flex-col gap-1.5">
            <motion.span
              animate={isOpen ? { rotate: 45, y: 5 } : { rotate: 0, y: 0 }}
              className="block h-0.5 w-5 bg-foreground"
            />
            <motion.span
              animate={isOpen ? { opacity: 0 } : { opacity: 1 }}
              className="block h-0.5 w-5 bg-foreground"
            />
            <motion.span
              animate={isOpen ? { rotate: -45, y: -5 } : { rotate: 0, y: 0 }}
              className="block h-0.5 w-5 bg-foreground"
            />
          </div>
        </button>
      </nav>

      {/* Mobile menu */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="mt-2 overflow-hidden rounded-xl border border-border bg-card md:hidden"
            id="mobile-nav-panel"
          >
            <div className="flex flex-col gap-1 p-4">
              <span className="truncate px-4 py-3 text-sm text-muted-foreground">{user.full_name || user.email}</span>
              <button type="button" onClick={() => { setIsOpen(false); onLogout(); }} className="cozy-button-secondary mt-2 inline-flex items-center justify-center gap-2 rounded-lg px-5 py-3 text-sm font-medium"><LogOut className="size-4" />Logout</button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.header>
  );
}
