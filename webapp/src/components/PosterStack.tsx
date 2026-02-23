import { motion, useMotionValue, useTransform, PanInfo } from "framer-motion";
import React, { useState, useEffect } from "react";

interface CardRotateProps {
  children: React.ReactNode;
  onSendToBack: () => void;
}

function CardRotate({ children, onSendToBack }: CardRotateProps) {
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const rotateX = useTransform(y, [-100, 100], [60, -60]);
  const rotateY = useTransform(x, [-100, 100], [-60, 60]);

  function handleDragEnd(_: any, info: PanInfo) {
    const threshold = 180;
    if (Math.abs(info.offset.x) > threshold || Math.abs(info.offset.y) > threshold) {
      onSendToBack();
    } else {
      x.set(0);
      y.set(0);
    }
  }

  return (
    <motion.div
      className="absolute h-72 w-48 cursor-grab"
      style={{ x, y, rotateX, rotateY }}
      drag
      dragConstraints={{ top: 0, right: 0, bottom: 0, left: 0 }}
      dragElastic={0.6}
      whileTap={{ cursor: "grabbing" }}
      onDragEnd={handleDragEnd}
      onClick={onSendToBack}
    >
      {children}
    </motion.div>
  );
}

export default function PosterStack({ posterUrls }: { posterUrls: string[] }) {
  const [cards, setCards] = useState(
    posterUrls.map((url, i) => ({
      id: i + 1,
      z: posterUrls.length - i,
      img: url,
    }))
  );

  // Update cards when posterUrls changes
  useEffect(() => {
    setCards(
      posterUrls.map((url, i) => ({
        id: i + 1,
        z: posterUrls.length - i,
        img: url,
      }))
    );
  }, [posterUrls]);

  const sendToBack = (id: number) => {
    setCards((prev) => {
      const newCards = [...prev];
      const index = newCards.findIndex((card) => card.id === id);
      const [card] = newCards.splice(index, 1);
      newCards.unshift(card);
      return newCards;
    });
  };

  return (
    <div className="relative h-96 w-64 mx-auto" style={{ perspective: 600 }}>
      {cards.map((card, index) => (
        <CardRotate key={card.id} onSendToBack={() => sendToBack(card.id)}>
          <motion.div
            className="h-full w-full object-cover rounded-lg border border-white/50 shadow-sm overflow-hidden"
            animate={{
              rotateZ: (cards.length - index - 1) * 6,
              scale: 1 + index * 0.04 - cards.length * 0.04,
              transformOrigin: "90% 90%",
            }}
            initial={false}
            transition={{ type: "spring", stiffness: 260, damping: 20 }}
          >
            <img
              src={card.img}
              alt={`Movie ${card.id}`}
              className="pointer-events-none h-full w-full object-cover"
            />
          </motion.div>
        </CardRotate>
      ))}
    </div>
  );
}
