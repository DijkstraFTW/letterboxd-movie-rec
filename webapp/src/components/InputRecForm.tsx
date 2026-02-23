import { useState } from "react"
import { Card } from "../../shadcn/components/ui/card.tsx"
import { Button } from "../../shadcn/components/ui/button.tsx"
import { MultipleSelector } from "../../shadcn/components/ui/multipleselector.tsx"
import { Slider } from "../../shadcn/components/ui/slider.tsx"
import { Label } from "../../shadcn/components/ui/label.tsx"

const genreOptions: { label: string; value: string }[] = [
  { label: "Action", value: "Action" },
  { label: "Action & Adventure", value: "Action & Adventure" },
  { label: "Adventure", value: "Adventure" },
  { label: "Animation", value: "Animation" },
  { label: "Comedy", value: "Comedy" },
  { label: "Crime", value: "Crime" },
  { label: "Documentary", value: "Documentary" },
  { label: "Drama", value: "Drama" },
  { label: "Family", value: "Family" },
  { label: "Fantasy", value: "Fantasy" },
  { label: "History", value: "History" },
  { label: "Horror", value: "Horror" },
  { label: "Kids", value: "Kids" },
  { label: "Music", value: "Music" },
  { label: "Mystery", value: "Mystery" },
  { label: "News", value: "News" },
  { label: "Reality", value: "Reality" },
  { label: "Romance", value: "Romance" },
  { label: "Sci-Fi & Fantasy", value: "Sci-Fi & Fantasy" },
  { label: "Science Fiction", value: "Science Fiction" },
  { label: "Soap", value: "Soap" },
  { label: "Talk", value: "Talk" },
  { label: "Thriller", value: "Thriller" },
  { label: "TV Movie", value: "TV Movie" },
  { label: "War", value: "War" },
  { label: "War & Politics", value: "War & Politics" },
  { label: "Western", value: "Western" },
]

interface InputRecFormProps {
  onSubmit: (genres: string[], minRating: number) => void;
}

export function InputRecForm({ onSubmit }: InputRecFormProps) {
  const [genres, setGenres] = useState<string[]>([])
  const [min_rating, setMinRating] = useState([5])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit(genres, min_rating[0])
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex items-center justify-center p-4 w-full"
    >
      <div className="grid w-full gap-4">
        <Card className="p-4 bg-[#111111] rounded-lg border-0 text-white/80">
          <h3 className="text-2xl text-white w-fit justify-left">
            No Letterboxd account?
          </h3>
          <p className="text-white/80">
            No problem! Select your favorite genres and minimum ratings
            so that we'll craft recommendations just for you.
          </p>

          <div className="mt-4">
            <MultipleSelector
              selectFirstItem={false}
              defaultOptions={genreOptions}
              placeholder="Select movie genres you like..."
              hidePlaceholderWhenSelected={true}
              onChange={(selected) => setGenres(selected.map((s) => s.value))}
            />
          </div>

          <div className="mt-6 mb-2 text-white/80 bg-[#1e1e1e] border-white/5 rounded-md p-3">
            <Label className="mt-2 mb-3 text-white/80">Minimum rating</Label>
            <Slider
              value={min_rating}
              onValueChange={setMinRating}
              min={0}
              max={10}
              step={0.5}
              className="mt-2 mb-2 p-2"
            />
          </div>

          <Button
            type="submit"
            disabled={genres.length === 0}
            className="mt-4 w-fit inline-flex items-center justify-center gap-2 whitespace-nowrap text-sm focus-visible:outline-none cursor-pointer disabled:pointer-events-none disabled:opacity-50 py-1.5 rounded-full px-4 h-8 bg-white text-black font-medium hover:bg-gray-100 transition-colors"
          >
            Proceed
          </Button>
        </Card>
      </div>
    </form>
  )
}
