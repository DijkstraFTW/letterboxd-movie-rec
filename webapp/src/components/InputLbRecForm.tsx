import { useState } from "react"
import { InfoIcon } from "lucide-react"

import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "../../shadcn/components/ui/input-group.tsx"
import { Label } from "../../shadcn/components/ui/label.tsx"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "../../shadcn/components/ui/tooltip.tsx"
import { Card } from "../../shadcn/components/ui/card.tsx"
import { Checkbox } from "../../shadcn/components/ui/checkbox.tsx"
import { Button } from "../../shadcn/components/ui/button.tsx"

interface InputLbRecFormProps {
  onSubmit: () => void;
}

export function InputLbRecForm({ onSubmit }: InputLbRecFormProps) {
  const [letterboxd_username, setLetterboxdUsername] = useState("")
  const [data_opt_in, setDataOptIn] = useState(true)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    console.log({ letterboxd_username, data_opt_in })
    onSubmit()
    // Replace with your actual API call:
    // const res = await fetch('/api/recommendations', { ... })
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex items-center justify-center p-4 w-full"
    >
      <div className="grid w-full gap-4">
        <Card className="p-4 bg-[#111111] rounded-lg border-0 text-white/80">
          <h3 className="text-2xl text-white w-fit">
            Personalized Recommendations
          </h3>
          <p className="mt-1 text-white/80">
            Enter your Letterboxd username to let us learn from your reviews and
            favorite films.
          </p>

          <InputGroup className="rounded-md bg-[#1e1e1e] border-0 p-2 mt-4">
            <InputGroupInput
              id="letterboxd_username"
              placeholder="schaffrillas"
              value={letterboxd_username}
              onChange={(e) => setLetterboxdUsername(e.target.value)}
              className="border-white/5"
            />
            <InputGroupAddon align="block-start" className="justify-between">
              <Label className="text-white" htmlFor="letterboxd_username">
                Letterboxd username
              </Label>
              <Tooltip>
                <TooltipTrigger>
                  <InputGroupButton
                    variant="ghost"
                    aria-label="Help"
                    className="ml-auto bg-white/5 hover:bg-white/10 hover:text-white/80 text-white/80 rounded-full"
                    size="icon-xs"
                  >
                    <InfoIcon />
                  </InputGroupButton>
                </TooltipTrigger>
                <TooltipContent>
                  We'll use this information to personalize your movie
                  recommendations
                </TooltipContent>
              </Tooltip>
            </InputGroupAddon>
          </InputGroup>

          <Label
            htmlFor="data_opt_in"
            className="mt-4 border-0 bg-[#1e1e1e] flex items-start gap-3 rounded-lg p-3 cursor-pointer has-[[aria-checked=true]]:bg-[#1e1e1e] has-[[aria-checked=true]]:border-blue-600"
          >
            <Checkbox
              id="data_opt_in"
              checked={data_opt_in}
              onCheckedChange={(checked) => setDataOptIn(!!checked)}
              className="border-white/5 data-[state=checked]:border-blue-600 data-[state=checked]:bg-blue-600 data-[state=checked]:text-white"
            />
            <div className="grid gap-1.5 font-normal">
              <p className="text-sm leading-none font-medium">
                Share your reviews
              </p>
              <p className="text-muted-foreground text-sm">
                Help us improve our model by using your review data.
              </p>
            </div>
          </Label>

          <Button
            type="submit"
            disabled={!letterboxd_username}
            className="mt-4 w-fit inline-flex items-center justify-center gap-2 whitespace-nowrap text-sm focus-visible:outline-none cursor-pointer disabled:pointer-events-none disabled:opacity-50 py-1.5 rounded-full px-4 h-8 bg-white text-black font-medium hover:bg-gray-100 transition-colors"
          >
            Proceed
          </Button>
        </Card>
      </div>
    </form>
  )
}
