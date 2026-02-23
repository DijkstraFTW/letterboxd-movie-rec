"use client"

import * as React from "react"
import * as SliderPrimitive from "@radix-ui/react-slider"
import { cn } from "../../lib/utils.ts"
import { StarFilledIcon } from "@radix-ui/react-icons"

function Slider({
  className,
  defaultValue = [5],
  min = 0,
  max = 10,
  step = 1,
  value: propValue,
  onValueChange: propOnValueChange,
  ...props
}: React.ComponentProps<typeof SliderPrimitive.Root>) {
  const [internalValue, setInternalValue] = React.useState(defaultValue)
  const isControlled = propValue !== undefined
  const value = isControlled ? propValue : internalValue

  const handleValueChange = (val: number[]) => {
    if (!isControlled) setInternalValue(val)
    propOnValueChange?.(val)
  }

  return (
    <div className="flex items-center gap-3 justify-center w-full">
      <SliderPrimitive.Root
        data-slot="slider"
        value={value}
        onValueChange={handleValueChange}
        min={min}
        max={max}
        step={step}
        className={cn(
          "relative flex w-full touch-none items-center select-none data-[disabled]:opacity-50",
          className
        )}
        {...props}
      >
        <SliderPrimitive.Track
          data-slot="slider-track"
          className={cn(
            "bg-white/50 relative grow overflow-hidden rounded-full h-1.5"
          )}
        >
          <SliderPrimitive.Range
            data-slot="slider-range"
            className="bg-blue-600 absolute h-full"
          />
        </SliderPrimitive.Track>
        <SliderPrimitive.Thumb
          data-slot="slider-thumb"
          className="border-primary ring-ring/50 block size-4 shrink-0 rounded-full border bg-white shadow-sm transition-[color,box-shadow] hover:ring-4 focus-visible:ring-4 focus-visible:outline-hidden"
        />
      </SliderPrimitive.Root>

      <div className="flex items-center gap-1 mt-1 text-sm font-light min-w-[3.5rem]">
        <span className="inline-block text-right min-w-[2rem]">{value[0]}</span>
        <StarFilledIcon className="inline-block w-4 h-4 text-white/50" />
      </div>
    </div>
  )
}

export { Slider }
