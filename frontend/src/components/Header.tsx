import { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {LogOut} from 'lucide-react';
import {User} from '../lib/api';

const navLinks = [
  { label: 'Analyze a job', href: '#analyze-job' },
];

export function Header({user, onLogout}: {user: User; onLogout: () => void}) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <motion.header
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      className="fixed top-0 left-0 right-0 z-50 px-6 py-4"
      id="app-header"
    >
      <nav className="mx-auto flex max-w-5xl items-center justify-between rounded-full border border-border/50 bg-background/80 px-6 py-3 backdrop-blur-xl shadow-lg shadow-black/10">
        <a href="/" className="flex items-center gap-2">
          <motion.span 
            className="text-lg font-medium tracking-tight text-foreground"
            whileHover={{ scale: 1.02 }}
          >
            career<span className="text-primary">OS</span>
          </motion.span>
        </a>

        {/* Desktop nav */}
        <div className="hidden items-center gap-8 md:flex">
          {navLinks.map((link, i) => (
            <motion.a
              key={link.href}
              href={link.href}
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 * i }}
              className="relative text-sm text-muted-foreground transition-colors duration-200 hover:text-foreground group"
            >
              {link.label}
              <span className="absolute -bottom-1 left-0 h-px w-0 bg-primary transition-all duration-300 group-hover:w-full" />
            </motion.a>
          ))}
        </div>

        <div className="hidden items-center gap-3 md:flex">
          <span className="max-w-44 truncate text-sm text-muted-foreground">{user.full_name || user.email}</span>
          <motion.button
            type="button"
            onClick={onLogout}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className="inline-flex items-center gap-2 rounded-full border border-border px-4 py-2 text-sm text-foreground transition hover:border-primary"
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
            className="mt-2 overflow-hidden rounded-2xl border border-border/50 bg-background/95 backdrop-blur-xl md:hidden"
            id="mobile-nav-panel"
          >
            <div className="flex flex-col gap-1 p-4">
              {navLinks.map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  onClick={() => setIsOpen(false)}
                  className="rounded-lg px-4 py-3 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                >
                  {link.label}
                </a>
              ))}
              <hr className="my-2 border-border" />
              <span className="truncate px-4 py-3 text-sm text-muted-foreground">{user.full_name || user.email}</span>
              <button type="button" onClick={() => { setIsOpen(false); onLogout(); }} className="mt-2 inline-flex items-center justify-center gap-2 rounded-full border border-border px-5 py-3 text-sm font-medium text-foreground"><LogOut className="size-4" />Logout</button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.header>
  );
}
