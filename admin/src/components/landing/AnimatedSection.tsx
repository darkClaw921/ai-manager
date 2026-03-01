import { motion } from 'framer-motion'
import type { ReactNode, CSSProperties } from 'react'

interface AnimatedSectionProps {
  children: ReactNode
  delay?: number
  className?: string
  style?: CSSProperties
}

export default function AnimatedSection({
  children,
  delay = 0,
  className,
  style,
}: AnimatedSectionProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 50 }}
      whileInView={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, delay }}
      viewport={{ once: true }}
      className={className}
      style={style}
    >
      {children}
    </motion.div>
  )
}
