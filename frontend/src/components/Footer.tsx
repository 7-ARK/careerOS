import { motion } from 'motion/react';

const footerLinks = {
  Product: [
    { label: 'Features', href: '#features' },
    { label: 'How it works', href: '#how-it-works' },
    { label: 'Changelog', href: '#' },
  ],
  Company: [
    { label: 'About', href: '#' },
    { label: 'Blog', href: '#' },
    { label: 'Contact', href: '#' },
  ],
  Resources: [
    { label: 'Help center', href: '#' },
    { label: 'Resume tips', href: '#' },
    { label: 'Career advice', href: '#' },
  ],
  Legal: [
    { label: 'Privacy Policy', href: '#' },
    { label: 'Terms of Use', href: '#' },
  ],
};

export function Footer() {
  return (
    <footer className="border-t border-border/40 bg-background px-6 py-16" id="app-footer">
      <div className="mx-auto max-w-5xl">
        <div className="grid gap-12 md:grid-cols-2 lg:grid-cols-5">
          {/* Brand column */}
          <div className="lg:col-span-1">
            <a href="/" className="inline-block">
              <span className="text-xl font-medium tracking-tight text-foreground">
                career<span className="text-primary">OS</span>
              </span>
            </a>
            <p className="mt-4 text-xs text-muted-foreground leading-relaxed">
              The professional career pipeline scheduler optimized for developers, managers, and designers.
            </p>
          </div>

          {/* Link columns */}
          {Object.entries(footerLinks).map(([category, links]) => (
            <div key={category}>
              <h4 className="mb-4 text-xs font-semibold uppercase tracking-wider text-foreground">
                {category}
              </h4>
              <ul className="space-y-2.5">
                {links.map((link) => (
                  <li key={link.label}>
                    <motion.a
                      href={link.href}
                      whileHover={{ x: 2, color: '#C9A86A' }}
                      className="text-xs text-muted-foreground transition-colors"
                    >
                      {link.label}
                    </motion.a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom bar */}
        <div className="mt-16 flex flex-col items-center justify-between gap-4 border-t border-border/10 pt-8 sm:flex-row">
          <p className="text-xs text-muted-foreground">
            &copy; {new Date().getFullYear()} careerOS. Built with modern React and Tailwind.
          </p>

          {/* Social links */}
          <div className="flex items-center gap-3">
            {['Twitter', 'LinkedIn', 'GitHub'].map((social) => (
              <motion.a
                key={social}
                href="#"
                whileHover={{ y: -2 }}
                className="text-xs font-mono text-muted-foreground hover:text-primary transition-colors uppercase tracking-widest"
              >
                {social}
              </motion.a>
            ))}
          </div>
        </div>
      </div>
    </footer>
  );
}
