import Header from "../components/Header.tsx";
import MovieGrid from "../components/MovieGrid.tsx";
import Footer from "../components/Footer.tsx";
import {Metrics} from "../components/Metrics.tsx";
import {Tabs, TabsContent, TabsList, TabsTrigger} from "../../shadcn/components/ui/tabs.tsx";


const movies: any[] = [{
    'movie_title_formatted': 'sicario-day-of-the-soldado',
    'movie_title': 'Sicario: Day of the Soldado',
    'type': 'movie',
    'year_released': 2018,
    'imdb_link': 'http://www.imdb.com/title/tt5052474/maindetails',
    'tmdb_link': 'https://www.themoviedb.org/movie/400535/',
    'imdb_id': 'tt5052474',
    'tmdb_id': '400535',
    'lb_rating': '3.2',
    'histogram': {
        '1.0': 492,
        '2.0': 1368,
        '3.0': 1940,
        '4.0': 7368,
        '5.0': 11509,
        '6.0': 29427,
        '7.0': 26942,
        '8.0': 17475,
        '9.0': 2922,
        '10.0': 2512,
        'fans': 68,
        'lb_rating': '3.2',
        'total': 101955
    },
    'poster_url': 'https://a.ltrbxd.com/resized/film-poster/3/3/5/2/9/4/335294-sicario-day-of-the-soldado-0-230-0-345-crop.jpg',
    'genres': ['Action', 'Crime', 'Thriller'],
    'production_countries': ['United States of America'],
    'spoken_languages': ['English', 'Español'],
    'popularity': 63.776,
    'overview': 'Agent Matt Graver teams up with operative Alejandro Gillick to prevent Mexican drug cartels from smuggling terrorists across the United States border.',
    'runtime': 122,
    'vote_average': 6.918,
    'vote_count': 3393,
    'release_date': '2018-06-27',
    'original_language': 'en',
    'themes': ['High speed and special ops', 'Politics and human rights', 'Crime, drugs and gangsters', 'Intense political and terrorist thrillers', 'Exciting spy thrillers with tense intrigue', 'Violent action, guns, and crime', 'Explosive and action-packed heroes vs. villains', 'Violent crime and drugs'],
    'nanogenres': ['Terrorism, Government, Cia', 'Thriller, Unpredictable, Unexpected', 'Powerful, Storytelling, Complexity', 'Violence, Dark, Unexpected', 'Friendship, Realism, Dangerous', 'Thriller, Terror, Dark', 'Villain, Bullets, Criminal', 'Terrorism, Attacks, Bombing', 'Villain, Cliche, Action-Packed', 'Killing, Shootings, Extreme']
}, {
    'movie_title_formatted': 'mission-impossible-iii',
    'movie_title': 'Mission: Impossible III',
    'type': 'movie',
    'year_released': 2006,
    'imdb_link': 'http://www.imdb.com/title/tt0317919/maindetails',
    'tmdb_link': 'https://www.themoviedb.org/movie/956/',
    'imdb_id': 'tt0317919',
    'tmdb_id': '956',
    'lb_rating': '3.3',
    'histogram': {
        '1.0': 530,
        '2.0': 1894,
        '3.0': 2340,
        '4.0': 12349,
        '5.0': 20584,
        '6.0': 79300,
        '7.0': 74869,
        '8.0': 54423,
        '9.0': 9461,
        '10.0': 8497,
        'fans': 136,
        'lb_rating': '3.3',
        'total': 264247
    },
    'poster_url': 'https://a.ltrbxd.com/resized/film-poster/5/1/2/0/4/51204-mission-impossible-iii-0-230-0-345-crop.jpg',
    'genres': ['Adventure', 'Action', 'Thriller'],
    'production_countries': ['United States of America'],
    'spoken_languages': ['Deutsch', 'English', 'Italiano', '普通话', 'Český', '广州话 / 廣州話'],
    'popularity': 49.344,
    'overview': 'Retired from active duty, and training recruits for the Impossible Mission Force, agent Ethan Hunt faces the toughest foe of his career: Owen Davian, an international broker of arms and information, who is as cunning as he is ruthless. Davian emerges to threaten Hunt and all that he holds dear -- including the woman Hunt loves.',
    'runtime': 126,
    'vote_average': 6.7,
    'vote_count': 6497,
    'release_date': '2006-04-25',
    'original_language': 'en',
    'themes': ['High speed and special ops', 'Epic heroes', 'Explosive and action-packed heroes vs. villains', 'Adrenaline-fueled action and fast cars', 'Exciting spy thrillers with tense intrigue', 'Superheroes in action-packed battles with villains', 'Intense political and terrorist thrillers'],
    'nanogenres': ['Action, Spy, Secret', 'Tense, Explosives, Bullets', 'Fighting, Shootout, Mindless', 'Suspense, Slick, Stylish', 'Suspense, Guns, Action-Packed', 'Stunts, Bullets, Speed', 'Jokes, Guns, Cool', 'Thriller, Explosives, Danger', 'Thrills, Stunts, Villain', 'Fighting, Thrills, Violence']
}, {
    'movie_title_formatted': 'dune-part-two',
    'movie_title': 'Dune: Part Two',
    'type': 'movie',
    'year_released': 2024,
    'imdb_link': 'http://www.imdb.com/title/tt15239678/maindetails',
    'tmdb_link': 'https://www.themoviedb.org/movie/693134/',
    'imdb_id': 'tt15239678',
    'tmdb_id': '693134',
    'lb_rating': '4.5',
    'histogram': {
        '1.0': 1415,
        '2.0': 2279,
        '3.0': 1593,
        '4.0': 7662,
        '5.0': 10964,
        '6.0': 44282,
        '7.0': 76174,
        '8.0': 264286,
        '9.0': 321268,
        '10.0': 613673,
        'fans': 46000,
        'lb_rating': '4.5',
        'total': 1343596
    },
    'poster_url': 'https://a.ltrbxd.com/resized/film-poster/6/1/7/4/4/3/617443-dune-part-two-0-230-0-345-crop.jpg',
    'genres': ['Science Fiction', 'Adventure'],
    'production_countries': ['United States of America'],
    'spoken_languages': ['English'],
    'popularity': 1618.076,
    'overview': 'Follow the mythic journey of Paul Atreides as he unites with Chani and the Fremen while on a path of revenge against the conspirators who destroyed his family. Facing a choice between the love of his life and the fate of the known universe, Paul endeavors to prevent a terrible future only he can foresee.',
    'runtime': 167,
    'vote_average': 8.3,
    'vote_count': 3286,
    'release_date': '2024-02-27',
    'original_language': 'en',
    'themes': ['Epic heroes', 'Humanity and the world around us', 'Superheroes in action-packed battles with villains', 'Action-packed space and alien sagas', 'Thought-provoking sci-fi action and future technology', 'Emotional and captivating fantasy storytelling', 'Historical battles and epic heroism'],
    'nanogenres': ['Space, Technology, Vision', 'Action, Epic, Emotion', 'Spaceship, Explosives, Destruction', 'Planet, Humanity, Future', 'Imaginative, Breathtaking, Technology', 'Future, Thought-Provoking, Philosophical', 'Suspense, Guns, Action-Packed', 'Fighting, Evil, Exciting', 'Hero, Future, Vision', 'Combat, Swords, Weapons']
}, {
    'movie_title_formatted': 'dune-2021',
    'movie_title': 'Dune',
    'type': 'movie',
    'year_released': 2021,
    'imdb_link': 'http://www.imdb.com/title/tt1160419/maindetails',
    'tmdb_link': 'https://www.themoviedb.org/movie/438631/',
    'imdb_id': 'tt1160419',
    'tmdb_id': '438631',
    'lb_rating': '3.9',
    'histogram': {
        '1.0': 7586,
        '2.0': 21709,
        '3.0': 10826,
        '4.0': 65934,
        '5.0': 57377,
        '6.0': 252563,
        '7.0': 281523,
        '8.0': 695835,
        '9.0': 333093,
        '10.0': 382719,
        'fans': 22000,
        'lb_rating': '3.9',
        'total': 2109165
    },
    'poster_url': 'https://a.ltrbxd.com/resized/sm/upload/nx/8b/vs/gc/cDbNAY0KM84cxXhmj8f0dLWza3t-0-230-0-345-crop.jpg',
    'genres': ['Science Fiction', 'Adventure'],
    'production_countries': ['United States of America'],
    'spoken_languages': ['普通话', 'English'],
    'popularity': 535.213,
    'overview': "Paul Atreides, a brilliant and gifted young man born into a great destiny beyond his understanding, must travel to the most dangerous planet in the universe to ensure the future of his family and his people. As malevolent forces explode into conflict over the planet's exclusive supply of the most precious resource in existence-a commodity capable of unlocking humanity's greatest potential-only those who can conquer their fear will survive.",
    'runtime': 155,
    'vote_average': 7.789,
    'vote_count': 11363,
    'release_date': '2021-09-15',
    'original_language': 'en',
    'themes': ['Epic heroes', 'Monsters, aliens, sci-fi and the apocalypse', 'Action-packed space and alien sagas', 'Thought-provoking sci-fi action and future technology', 'Superheroes in action-packed battles with villains', 'Imaginative space odysseys and alien encounters', 'Emotional and captivating fantasy storytelling'],
    'nanogenres': ['Space, Technology, Vision', 'Action, Epic, Emotion', 'Spaceship, Explosives, Destruction', 'Fighting, Killing, Evil', 'Explosives, Cool, Exciting', 'Cool, Monster, Darkness', 'Battle, Destruction, Weapons', 'Weird, Chilling, Mystery', 'Graphics, Anticipation, Creativity', 'Predictable, Wins, Gorgeous']
}, {
    'movie_title_formatted': 'dune-part-two',
    'movie_title': 'Dune: Part Two',
    'type': 'movie',
    'year_released': 2024,
    'imdb_link': 'http://www.imdb.com/title/tt15239678/maindetails',
    'tmdb_link': 'https://www.themoviedb.org/movie/693134/',
    'imdb_id': 'tt15239678',
    'tmdb_id': '693134',
    'lb_rating': '4.5',
    'histogram': {
        '1.0': 1415,
        '2.0': 2279,
        '3.0': 1593,
        '4.0': 7662,
        '5.0': 10964,
        '6.0': 44282,
        '7.0': 76174,
        '8.0': 264286,
        '9.0': 321268,
        '10.0': 613673,
        'fans': 46000,
        'lb_rating': '4.5',
        'total': 1343596
    },
    'poster_url': 'https://a.ltrbxd.com/resized/film-poster/6/1/7/4/4/3/617443-dune-part-two-0-230-0-345-crop.jpg',
    'genres': ['Science Fiction', 'Adventure'],
    'production_countries': ['United States of America'],
    'spoken_languages': ['English'],
    'popularity': 1618.076,
    'overview': 'Follow the mythic journey of Paul Atreides as he unites with Chani and the Fremen while on a path of revenge against the conspirators who destroyed his family. Facing a choice between the love of his life and the fate of the known universe, Paul endeavors to prevent a terrible future only he can foresee.',
    'runtime': 167,
    'vote_average': 8.3,
    'vote_count': 3286,
    'release_date': '2024-02-27',
    'original_language': 'en',
    'themes': ['Epic heroes', 'Humanity and the world around us', 'Superheroes in action-packed battles with villains', 'Action-packed space and alien sagas', 'Thought-provoking sci-fi action and future technology', 'Emotional and captivating fantasy storytelling', 'Historical battles and epic heroism'],
    'nanogenres': ['Space, Technology, Vision', 'Action, Epic, Emotion', 'Spaceship, Explosives, Destruction', 'Planet, Humanity, Future', 'Imaginative, Breathtaking, Technology', 'Future, Thought-Provoking, Philosophical', 'Suspense, Guns, Action-Packed', 'Fighting, Evil, Exciting', 'Hero, Future, Vision', 'Combat, Swords, Weapons']
}, {
    'movie_title_formatted': 'dune-2021',
    'movie_title': 'Dune',
    'type': 'movie',
    'year_released': 2021,
    'imdb_link': 'http://www.imdb.com/title/tt1160419/maindetails',
    'tmdb_link': 'https://www.themoviedb.org/movie/438631/',
    'imdb_id': 'tt1160419',
    'tmdb_id': '438631',
    'lb_rating': '3.9',
    'histogram': {
        '1.0': 7586,
        '2.0': 21709,
        '3.0': 10826,
        '4.0': 65934,
        '5.0': 57377,
        '6.0': 252563,
        '7.0': 281523,
        '8.0': 695835,
        '9.0': 333093,
        '10.0': 382719,
        'fans': 22000,
        'lb_rating': '3.9',
        'total': 2109165
    },
    'poster_url': 'https://a.ltrbxd.com/resized/sm/upload/nx/8b/vs/gc/cDbNAY0KM84cxXhmj8f0dLWza3t-0-230-0-345-crop.jpg',
    'genres': ['Science Fiction', 'Adventure'],
    'production_countries': ['United States of America'],
    'spoken_languages': ['普通话', 'English'],
    'popularity': 535.213,
    'overview': "Paul Atreides, a brilliant and gifted young man born into a great destiny beyond his understanding, must travel to the most dangerous planet in the universe to ensure the future of his family and his people. As malevolent forces explode into conflict over the planet's exclusive supply of the most precious resource in existence-a commodity capable of unlocking humanity's greatest potential-only those who can conquer their fear will survive.",
    'runtime': 155,
    'vote_average': 7.789,
    'vote_count': 11363,
    'release_date': '2021-09-15',
    'original_language': 'en',
    'themes': ['Epic heroes', 'Monsters, aliens, sci-fi and the apocalypse', 'Action-packed space and alien sagas', 'Thought-provoking sci-fi action and future technology', 'Superheroes in action-packed battles with villains', 'Imaginative space odysseys and alien encounters', 'Emotional and captivating fantasy storytelling'],
    'nanogenres': ['Space, Technology, Vision', 'Action, Epic, Emotion', 'Spaceship, Explosives, Destruction', 'Fighting, Killing, Evil', 'Explosives, Cool, Exciting', 'Cool, Monster, Darkness', 'Battle, Destruction, Weapons', 'Weird, Chilling, Mystery', 'Graphics, Anticipation, Creativity', 'Predictable, Wins, Gorgeous']
}, {
    'movie_title_formatted': 'past-lives',
    'movie_title': 'Past Lives',
    'type': 'movie',
    'year_released': 2023,
    'imdb_link': 'http://www.imdb.com/title/tt13238346/maindetails',
    'tmdb_link': 'https://www.themoviedb.org/movie/666277/',
    'imdb_id': 'tt13238346',
    'tmdb_id': '666277',
    'lb_rating': '4.2',
    'histogram': {
        '1.0': 1219,
        '2.0': 2546,
        '3.0': 2120,
        '4.0': 10840,
        '5.0': 14942,
        '6.0': 59817,
        '7.0': 93778,
        '8.0': 259379,
        '9.0': 180620,
        '10.0': 248161,
        'fans': 23000,
        'lb_rating': '4.2',
        'total': 873422
    },
    'poster_url': 'https://a.ltrbxd.com/resized/film-poster/5/9/1/0/5/3/591053-past-lives-0-230-0-345-crop.jpg',
    'genres': ['Drama', 'Romance'],
    'production_countries': ['South Korea', 'United States of America'],
    'spoken_languages': ['English', '한국어/조선말'],
    'popularity': 93.056,
    'overview': 'Nora and Hae Sung, two childhood friends, are reunited in New York for one fateful week as they confront notions of destiny, love, and the choices that make a life.',
    'runtime': 106,
    'vote_average': 7.798,
    'vote_count': 1239,
    'release_date': '2023-06-02',
    'original_language': 'en',
    'themes': ['Moving relationship stories', 'Touching and sentimental family stories', 'Powerful stories of heartbreak and suffering', 'Captivating relationships and charming romance', 'Tragic sadness and captivating beauty', 'Passion and romance'],
    'nanogenres': ['Feelings, Moving, Crying', 'Drama, Cry, Endearing', 'Touching, Chemistry, Marriage', 'Romance, Sympathy, Desire', 'Relationships, Storytelling, Complexity', 'Relationships, Friendship, Sweet', 'Touching, Beauty, Desire', 'Powerful, Loving, Sentimental', 'Cry, Confused, Child', 'Charming, Magic, Dream']
}, {
    'movie_title_formatted': 'the-talented-mr-ripley',
    'movie_title': 'The Talented Mr. Ripley',
    'type': 'movie',
    'year_released': 1999,
    'imdb_link': 'http://www.imdb.com/title/tt0134119/maindetails',
    'tmdb_link': 'https://www.themoviedb.org/movie/1213/',
    'imdb_id': 'tt0134119',
    'tmdb_id': '1213',
    'lb_rating': '3.8',
    'histogram': {
        '1.0': 414,
        '2.0': 1215,
        '3.0': 1222,
        '4.0': 6486,
        '5.0': 9562,
        '6.0': 41864,
        '7.0': 65258,
        '8.0': 108969,
        '9.0': 37067,
        '10.0': 32404,
        'fans': 4800,
        'lb_rating': '3.8',
        'total': 304461
    },
    'poster_url': 'https://a.ltrbxd.com/resized/film-poster/5/1/1/3/8/51138-the-talented-mr-ripley-0-230-0-345-crop.jpg',
    'genres': ['Thriller', 'Crime', 'Drama'],
    'production_countries': ['United States of America'],
    'spoken_languages': ['English', 'Italiano'],
    'popularity': 37.922,
    'overview': "Tom Ripley is a calculating young man who believes it's better to be a fake somebody than a real nobody. Opportunity knocks in the form of a wealthy U.S. shipbuilder who hires Tom to travel to Italy to bring back his playboy son, Dickie. Ripley worms his way into the idyllic lives of Dickie and his girlfriend, plunging into a daring scheme of duplicity, lies and murder.",
    'runtime': 139,
    'vote_average': 7.188,
    'vote_count': 3482,
    'release_date': '1999-12-25',
    'original_language': 'en',
    'themes': ['Intense violence and sexual transgression', 'Humanity and the world around us', 'Thrillers and murder mysteries', 'Twisted dark psychological thriller', 'Intriguing and suspenseful murder mysteries', 'Suspenseful crime thrillers', 'Captivating relationships and charming romance', 'Noir and dark crime dramas'],
    'nanogenres': ['Weird, Disturbing, Intriguing', 'Suspense, Unexpected, Engaging', 'Murderer, Compelling, Sympathy', 'Romance, Sensitive, Lonely', 'Thriller, Psychotic, Dark', 'Suspense, Criminal, Film-Noir', 'Victim, Tense, Detective', 'Drama, Gripping, Vulnerable', 'Murder, Frighten, Mysterious', 'Detective, Twisted, Disturbed']
}, {
    'movie_title_formatted': 'joker-2019',
    'movie_title': 'Joker',
    'type': 'movie',
    'year_released': 2019,
    'imdb_link': 'http://www.imdb.com/title/tt7286456/maindetails',
    'tmdb_link': 'https://www.themoviedb.org/movie/475557/',
    'imdb_id': 'tt7286456',
    'tmdb_id': '475557',
    'lb_rating': '3.8',
    'histogram': {
        '1.0': 9828,
        '2.0': 25508,
        '3.0': 16395,
        '4.0': 86737,
        '5.0': 73912,
        '6.0': 334163,
        '7.0': 306361,
        '8.0': 822871,
        '9.0': 298212,
        '10.0': 596197,
        'fans': 22000,
        'lb_rating': '3.8',
        'total': 2570184
    },
    'poster_url': 'https://a.ltrbxd.com/resized/film-poster/4/0/6/7/7/5/406775-joker-0-230-0-345-crop.jpg',
    'genres': ['Crime', 'Thriller', 'Drama'],
    'production_countries': ['Canada', 'United States of America'],
    'spoken_languages': ['English'],
    'popularity': 312.884,
    'overview': 'During the 1980s, a failed stand-up comedian is driven insane and turns to a life of crime and chaos in Gotham City while becoming an infamous psychopathic crime figure.',
    'runtime': 122,
    'vote_average': 8.161,
    'vote_count': 24452,
    'release_date': '2019-10-01',
    'original_language': 'en',
    'themes': ['Intense violence and sexual transgression', 'Moving relationship stories', 'Humanity and the world around us', 'Crime, drugs and gangsters', 'Powerful stories of heartbreak and suffering', 'Gripping, intense violent crime', 'Challenging or sexual themes & twists', 'Emotional and captivating fantasy storytelling', 'Graphic violence and brutal revenge'],
    'nanogenres': ['Comic-Book, Hero, Exciting', 'Gory, Brutal, Extreme', 'Terrifying, Disturbed, Troubled', 'Chilling, Fear, Extreme', 'Shootings, Troubled, Confused', 'Emotion, Insanity, Mentally', 'Tense, Captivating, Unpredictable', 'Bloody, Dark, Intense', 'Intense, Storytelling, Compelling', 'Emotional, Madness, Sympathy']
}, {
    'movie_title_formatted': 'the-social-network',
    'movie_title': 'The Social Network',
    'type': 'movie',
    'year_released': 2010,
    'imdb_link': 'http://www.imdb.com/title/tt1285016/maindetails',
    'tmdb_link': 'https://www.themoviedb.org/movie/37799/',
    'imdb_id': 'tt1285016',
    'tmdb_id': '37799',
    'lb_rating': '4.0',
    'histogram': {
        '1.0': 2701,
        '2.0': 9573,
        '3.0': 5307,
        '4.0': 44698,
        '5.0': 36360,
        '6.0': 226230,
        '7.0': 197799,
        '8.0': 480848,
        '9.0': 200002,
        '10.0': 306040,
        'fans': 30000,
        'lb_rating': '4.0',
        'total': 1509558
    },
    'poster_url': 'https://a.ltrbxd.com/resized/sm/upload/nw/cm/pa/ai/sGQv3ZMZBDBnl3z42Q0mEQ5uiDe-0-230-0-345-crop.jpg',
    'genres': ['Drama'],
    'production_countries': ['United States of America'],
    'spoken_languages': ['English'],
    'popularity': 53.328,
    'overview': 'In 2003, Harvard undergrad and computer genius Mark Zuckerberg begins work on a new concept that eventually turns into the global social network known as Facebook. Six years later, he is one of the youngest billionaires ever, but Zuckerberg finds that his unprecedented success leads to both personal and legal complications when he ends up on the receiving end of two lawsuits, one involving his former friend.',
    'runtime': 121,
    'vote_average': 7.364,
    'vote_count': 11653,
    'release_date': '2010-10-01',
    'original_language': 'en',
    'themes': ['Humanity and the world around us', 'Teen school antics and laughter', 'Student coming-of-age challenges', 'Fascinating, emotional stories and documentaries'],
    'nanogenres': ['Geeks, Technology, Excitement', 'Relationships, Geeks, Obsession', 'Emotional, Biography, Facts', 'Cliche, College, School', 'College, Nerds, Silly', 'College, Girlfriend, Lesson', 'Drama, Sympathy, Complicated', 'Humor, Geeks, Cool', 'Friendship, Captivating, Soul', 'Cool, Intelligent, Stereotype']
}, {
    'movie_title_formatted': 'oppenheimer-2023',
    'movie_title': 'Oppenheimer',
    'type': 'movie',
    'year_released': 2023,
    'imdb_link': 'http://www.imdb.com/title/tt15398776/maindetails',
    'tmdb_link': 'https://www.themoviedb.org/movie/872585/',
    'imdb_id': 'tt15398776',
    'tmdb_id': '872585',
    'lb_rating': '4.2',
    'histogram': {
        '1.0': 4333,
        '2.0': 9102,
        '3.0': 5467,
        '4.0': 31577,
        '5.0': 32688,
        '6.0': 146631,
        '7.0': 181551,
        '8.0': 542159,
        '9.0': 446328,
        '10.0': 678678,
        'fans': 31000,
        'lb_rating': '4.2',
        'total': 2078514
    },
    'poster_url': 'https://a.ltrbxd.com/resized/film-poster/7/8/4/3/2/8/784328-oppenheimer-0-230-0-345-crop.jpg',
    'genres': ['Drama', 'History'],
    'production_countries': ['United Kingdom', 'United States of America'],
    'spoken_languages': ['Nederlands', 'English'],
    'popularity': 477.921,
    'overview': "The story of J. Robert Oppenheimer's role in the development of the atomic bomb during World War II.",
    'runtime': 181,
    'vote_average': 8.108,
    'vote_count': 7733,
    'release_date': '2023-07-19',
    'original_language': 'en',
    'themes': ['Humanity and the world around us', 'Politics and human rights', 'Epic history and literature', 'Intense political and terrorist thrillers', 'Riveting political and presidential drama', 'Dangerous technology and the apocalypse', 'Surreal and thought-provoking visions of life and death', 'Political drama, patriotism, and war'],
    'nanogenres': ['Intelligent, Thought-Provoking, Philosophical', 'Moving, Struggles, Riveting', 'Scientific, Thought-Provoking, Philosophy', 'Tear-Jerker, Breathtaking, Captivating', 'England, Civilian, Gripping', 'Touching, Historic, Nation', 'Reality, Revelation, Intellectual', 'Emotion, Humanity, Complexity', 'Thought-Provoking, Moral, Intellectual', 'Intense, Revelation, Fascinating']
}, {
    'movie_title_formatted': 'the-prestige',
    'movie_title': 'The Prestige',
    'type': 'movie',
    'year_released': 2006,
    'imdb_link': 'http://www.imdb.com/title/tt0482571/maindetails',
    'tmdb_link': 'https://www.themoviedb.org/movie/1124/',
    'imdb_id': 'tt0482571',
    'tmdb_id': '1124',
    'lb_rating': '4.2',
    'histogram': {
        '1.0': 847,
        '2.0': 2232,
        '3.0': 1787,
        '4.0': 10193,
        '5.0': 12243,
        '6.0': 63499,
        '7.0': 95556,
        '8.0': 275349,
        '9.0': 187111,
        '10.0': 227180,
        'fans': 22000,
        'lb_rating': '4.2',
        'total': 875997
    },
    'poster_url': 'https://a.ltrbxd.com/resized/film-poster/5/1/1/4/7/51147-the-prestige-0-230-0-345-crop.jpg',
    'genres': ['Drama', 'Mystery', 'Science Fiction'],
    'production_countries': ['United Kingdom', 'United States of America'],
    'spoken_languages': ['English'],
    'popularity': 80.535,
    'overview': 'A mysterious story of two magicians whose intense rivalry leads them on a life-long battle for supremacy -- full of obsession, deceit and jealousy with dangerous and deadly consequences.',
    'runtime': 130,
    'vote_average': 8.2,
    'vote_count': 15386,
    'release_date': '2006-10-19',
    'original_language': 'en',
    'themes': ['Thrillers and murder mysteries', 'Twisted dark psychological thriller', 'Intriguing and suspenseful murder mysteries', 'Intense political and terrorist thrillers'],
    'nanogenres': ['Dark, Storytelling, Captivating', 'Twist, Intriguing, Confusion', 'Twist, Sinister, Secret', 'Thriller, Climax, Riveting', 'Guessing, Thought-Provoking, Confusion', 'Tense, Mysterious, Solving', 'Suspense, Confused, Discover', 'Chemistry, Storytelling, Lover', 'Killing, Twist, Confused', 'Dark, Desire, Twisted']
}, {
    'movie_title_formatted': 'mission-impossible-dead-reckoning-part-one',
    'movie_title': 'Mission: Impossible – Dead Reckoning Part One',
    'type': 'movie',
    'year_released': 2023,
    'imdb_link': 'http://www.imdb.com/title/tt9603212/maindetails',
    'tmdb_link': 'https://www.themoviedb.org/movie/575264/',
    'imdb_id': 'tt9603212',
    'tmdb_id': '575264',
    'lb_rating': '3.7',
    'histogram': {
        '1.0': 1075,
        '2.0': 2636,
        '3.0': 2681,
        '4.0': 11583,
        '5.0': 17897,
        '6.0': 62032,
        '7.0': 95365,
        '8.0': 162992,
        '9.0': 62763,
        '10.0': 39657,
        'fans': 636,
        'lb_rating': '3.7',
        'total': 458681
    },
    'poster_url': 'https://a.ltrbxd.com/resized/film-poster/5/0/3/4/0/2/503402-mission-impossible-dead-reckoning-part-one-0-230-0-345-crop.jpg',
    'genres': ['Action', 'Thriller'],
    'production_countries': ['United States of America'],
    'spoken_languages': ['Français', 'English', 'Italiano', 'Pусский'],
    'popularity': 171.482,
    'overview': "Ethan Hunt and his IMF team embark on their most dangerous mission yet: To track down a terrifying new weapon that threatens all of humanity before it falls into the wrong hands. With control of the future and the world's fate at stake and dark forces from Ethan's past closing in, a deadly race around the globe begins. Confronted by a mysterious, all-powerful enemy, Ethan must consider that nothing can matter more than his mission—not even the lives of those he cares about most.",
    'runtime': 164,
    'vote_average': 7.55,
    'vote_count': 3342,
    'release_date': '2023-07-08',
    'original_language': 'en',
    'themes': ['High speed and special ops', 'Epic heroes', 'Explosive and action-packed heroes vs. villains', 'Adrenaline-fueled action and fast cars', 'Superheroes in action-packed battles with villains', 'Exciting spy thrillers with tense intrigue', 'Heists and thrilling action'],
    'nanogenres': ['Action, Spy, Secret', 'Gadgets, Stunts, Agent', 'Fighting, Cool, Menacing', 'Thriller, Explosives, Danger', 'Jokes, Guns, Cool', 'Death, Stunts, Formulaic', 'Action, Thrills, Shootings', 'Thrills, Stunts, Villain', 'Stunts, Cars, Chasing', 'Villain, Cool, Chases']
}, {
    'movie_title_formatted': 'avatar-the-way-of-water',
    'movie_title': 'Avatar: The Way of Water',
    'type': 'movie',
    'year_released': 2022,
    'imdb_link': 'http://www.imdb.com/title/tt1630029/maindetails',
    'tmdb_link': 'https://www.themoviedb.org/movie/76600/',
    'imdb_id': 'tt1630029',
    'tmdb_id': '76600',
    'lb_rating': '3.6',
    'histogram': {
        '1.0': 8013,
        '2.0': 18840,
        '3.0': 13763,
        '4.0': 59089,
        '5.0': 63137,
        '6.0': 201025,
        '7.0': 206460,
        '8.0': 339319,
        '9.0': 127502,
        '10.0': 186852,
        'fans': 6300,
        'lb_rating': '3.6',
        'total': 1224000
    },
    'poster_url': 'https://a.ltrbxd.com/resized/film-poster/6/3/0/5/8/63058-avatar-the-way-of-water-0-230-0-345-crop.jpg',
    'genres': ['Science Fiction', 'Adventure', 'Action'],
    'production_countries': ['United States of America'],
    'spoken_languages': ['English'],
    'popularity': 204.651,
    'overview': 'Set more than a decade after the events of the first film, learn the story of the Sully family (Jake, Neytiri, and their kids), the trouble that follows them, the lengths they go to keep each other safe, the battles they fight to stay alive, and the tragedies they endure.',
    'runtime': 192,
    'vote_average': 7.626,
    'vote_count': 11200,
    'release_date': '2022-12-14',
    'original_language': 'en',
    'themes': ['Monsters, aliens, sci-fi and the apocalypse', 'Epic heroes', 'Thought-provoking sci-fi action and future technology', 'Superheroes in action-packed battles with villains', 'Epic adventure and breathtaking battles', 'Emotional and captivating fantasy storytelling', 'Action-packed space and alien sagas'],
    'nanogenres': ['Emotional, Child, Wild', 'Tear-Jerker, Humans, Environment', 'Tear-Jerker, Magic, Captivating', 'Excitement, Engaging, Danger', 'Cry, Family, Environment', 'Touching, Breathtaking, Beauty', 'Touching, Tragic, Humanity', 'Action, Epic, Emotion', 'Action, Creature, Graphics', 'Adventure, Graphics, Fantasy']
}, {
    'movie_title_formatted': 'creed-iii',
    'movie_title': 'Creed III',
    'type': 'movie',
    'year_released': 2023,
    'imdb_link': 'http://www.imdb.com/title/tt11145118/maindetails',
    'tmdb_link': 'https://www.themoviedb.org/movie/677179/',
    'imdb_id': 'tt11145118',
    'tmdb_id': '677179',
    'lb_rating': '3.5',
    'histogram': {
        '1.0': 484,
        '2.0': 1474,
        '3.0': 1945,
        '4.0': 9026,
        '5.0': 16345,
        '6.0': 54712,
        '7.0': 69333,
        '8.0': 74733,
        '9.0': 19099,
        '10.0': 14133,
        'fans': 329,
        'lb_rating': '3.5',
        'total': 261284
    },
    'poster_url': 'https://a.ltrbxd.com/resized/film-poster/6/0/1/6/2/4/601624-creed-iii-0-230-0-345-crop.jpg',
    'genres': ['Drama', 'Action'],
    'production_countries': ['United States of America'],
    'spoken_languages': ['Español', 'English'],
    'popularity': 128.241,
    'overview': 'After dominating the boxing world, Adonis Creed has thrived in his career and family life. When a childhood friend and former boxing prodigy, Damian Anderson, resurfaces after serving a long sentence in prison, he is eager to prove that he deserves his shot in the ring. The face-off between former friends is more than just a fight. To settle the score, Adonis must put his future on the line to battle Damian — a fighter with nothing to lose.',
    'runtime': 116,
    'vote_average': 7.125,
    'vote_count': 2323,
    'release_date': '2023-03-01',
    'original_language': 'en',
    'themes': ['Moving relationship stories', 'Underdog fighting and boxing stories'],
    'nanogenres': ['Boxing, Emotional, Sports', 'Fighter, Intense, Fought', 'Relationships, Dream, Desire', 'Predictable, Wins, Gorgeous', 'Compelling, Glory, Beloved', 'Fighter, Gritty, Wins', 'Cliche, Fighter, Flashy', 'Brutal, Battle, Fists', 'Feelings, Tragic, Anger', 'Touching, Storytelling, Flashy']
}, {
    'movie_title_formatted': 'babylon-2022',
    'movie_title': 'Babylon',
    'type': 'movie',
    'year_released': 2022,
    'imdb_link': 'http://www.imdb.com/title/tt10640346/maindetails',
    'tmdb_link': 'https://www.themoviedb.org/movie/615777/',
    'imdb_id': 'tt10640346',
    'tmdb_id': '615777',
    'lb_rating': '3.8',
    'histogram': {
        '1.0': 3264,
        '2.0': 7172,
        '3.0': 5782,
        '4.0': 21624,
        '5.0': 24907,
        '6.0': 69904,
        '7.0': 88239,
        '8.0': 165400,
        '9.0': 99495,
        '10.0': 109573,
        'fans': 16000,
        'lb_rating': '3.8',
        'total': 595360
    },
    'poster_url': 'https://a.ltrbxd.com/resized/film-poster/5/4/2/7/7/3/542773-babylon-0-230-0-345-crop.jpg',
    'genres': ['Drama', 'Comedy'],
    'production_countries': ['United States of America'],
    'spoken_languages': ['广州话 / 廣州話', 'English', 'Español'],
    'popularity': 235.223,
    'overview': "A tale of outsized ambition and outrageous excess, tracing the rise and fall of multiple characters in an era of unbridled decadence and depravity during Hollywood's transition from silent films to sound films in the late 1920s.",
    'runtime': 189,
    'vote_average': 7.411,
    'vote_count': 2763,
    'release_date': '2022-12-22',
    'original_language': 'en',
    'themes': ['Humanity and the world around us', 'Moving relationship stories', 'Emotional life of renowned artists'],
    'nanogenres': ['Emotion, Sexual, Passionate', 'Drugs, Depressing, Raw', 'Sexual, Weird, Genius', 'Hilarious, Sexual, Naked', 'Tear-Jerker, Beauty, Happiness', 'Emotion, Captivating, Desire', 'Chemistry, Gorgeous, Magic', 'Hilarious, Nudity, Fame', 'Emotion, Discover, Overcome', 'Predictable, Sadness, Crying']
}, {
    'movie_title_formatted': 'mr-mme-adelman',
    'movie_title': 'Mr & Mme Adelman',
    'type': 'movie',
    'year_released': 2017,
    'imdb_link': 'http://www.imdb.com/title/tt6095616/maindetails',
    'tmdb_link': 'https://www.themoviedb.org/movie/431937/',
    'imdb_id': 'tt6095616',
    'tmdb_id': '431937',
    'lb_rating': '3.7',
    'histogram': {
        '1.0': 27,
        '2.0': 55,
        '3.0': 46,
        '4.0': 190,
        '5.0': 290,
        '6.0': 873,
        '7.0': 1276,
        '8.0': 2115,
        '9.0': 696,
        '10.0': 969,
        'fans': 162,
        'lb_rating': '3.7',
        'total': 6537
    },
    'poster_url': 'https://a.ltrbxd.com/resized/film-poster/3/6/5/0/7/0/365070-mr-mme-adelman-0-230-0-345-crop.jpg',
    'themes': [],
    'nanogenres': [],
    'genres': ['Romance', 'Drama', 'Comedy'],
    'production_countries': ['Belgium', 'France'],
    'spoken_languages': ['Français'],
    'popularity': 19.138,
    'overview': "How did Sarah and Victor get along for more than 45 years? Who was this enigmatic woman living in the shadow of her husband? Love, ambition, betrayals and secrets feed the story of this extraordinary couple, as they experience both the large and small moments of the last century's history.",
    'runtime': 120,
    'vote_average': 7.5,
    'vote_count': 425,
    'release_date': '2017-03-08',
    'original_language': 'fr',
}, {
    'movie_title_formatted': 'lord-of-war',
    'movie_title': 'Lord of War',
    'type': 'movie',
    'year_released': 2005,
    'imdb_link': 'http://www.imdb.com/title/tt0399295/maindetails',
    'tmdb_link': 'https://www.themoviedb.org/movie/1830/',
    'imdb_id': 'tt0399295',
    'tmdb_id': '1830',
    'lb_rating': '3.6',
    'histogram': {
        '1.0': 277,
        '2.0': 767,
        '3.0': 984,
        '4.0': 4348,
        '5.0': 6981,
        '6.0': 24575,
        '7.0': 31914,
        '8.0': 33542,
        '9.0': 7693,
        '10.0': 6359,
        'fans': 379,
        'lb_rating': '3.6',
        'total': 117440
    },
    'poster_url': 'https://a.ltrbxd.com/resized/film-poster/5/0/7/6/9/50769-lord-of-war-0-230-0-345-crop.jpg',
    'genres': ['Crime', 'Drama', 'Thriller'],
    'production_countries': ['France', 'United States of America', 'Germany'],
    'spoken_languages': ['العربية', 'Deutsch', 'English', 'Français', 'Pусский', 'Español', 'Український', 'Türkçe'],
    'popularity': 29.464,
    'overview': "Yuri Orlov is a globetrotting arms dealer and, through some of the deadliest war zones, he struggles to stay one step ahead of a relentless Interpol agent, his business rivals and even some of his customers who include many of the world's most notorious dictators. Finally, he must also face his own conscience.",
    'runtime': 122,
    'vote_average': 7.31,
    'vote_count': 4544,
    'release_date': '2005-09-16',
    'original_language': 'en',
    'themes': ['Politics and human rights', 'Crime, drugs and gangsters', 'Intense violence and sexual transgression', 'Intense political and terrorist thrillers', 'Gritty crime and ruthless gangsters', 'Riveting political and presidential drama', 'Violent crime and drugs', 'Racism and the powerful fight for justice'],
    'nanogenres': ['Addiction, Moral, Society', 'Drama, Morality, Cynical', 'Shootings, Firearms, Weapons', 'Violence, Guns, Dangerous', 'Crime, Government, Moving', 'Anti-War, Enemies, Fighter', 'Thriller, Guns, Exciting', 'Gangster, Class, Crazy', 'Gangster, Violence, Drama', 'Blood, Exciting, Deadly']
}, {
    'movie_title_formatted': 'the-menu-2022',
    'movie_title': 'The Menu',
    'type': 'movie',
    'year_released': 2022,
    'imdb_link': 'http://www.imdb.com/title/tt9764362/maindetails',
    'tmdb_link': 'https://www.themoviedb.org/movie/593643/',
    'imdb_id': 'tt9764362',
    'tmdb_id': '593643',
    'lb_rating': '3.5',
    'histogram': {
        '1.0': 4959,
        '2.0': 16108,
        '3.0': 13302,
        '4.0': 73847,
        '5.0': 84471,
        '6.0': 323303,
        '7.0': 344505,
        '8.0': 515892,
        '9.0': 134174,
        '10.0': 155505,
        'fans': 4700,
        'lb_rating': '3.5',
        'total': 1666066
    },
    'poster_url': 'https://a.ltrbxd.com/resized/film-poster/5/2/1/3/2/3/521323-the-menu-0-230-0-345-crop.jpg',
    'genres': ['Comedy', 'Thriller', 'Horror'],
    'production_countries': ['United States of America'],
    'spoken_languages': ['English', 'Español'],
    'popularity': 82.161,
    'overview': 'A young couple travels to a remote island to eat at an exclusive restaurant where the chef has prepared a lavish menu, with some shocking surprises.',
    'runtime': 107,
    'vote_average': 7.192,
    'vote_count': 4342,
    'release_date': '2022-11-17',
    'original_language': 'en',
    'themes': ['Intense violence and sexual transgression', 'Humanity and the world around us', 'Twisted dark psychological thriller', 'Terrifying, haunted, and supernatural horror'],
    'nanogenres': ['Twist, Psychopath, Madness', 'Humor, Eating, Mocking', 'Killing, Shock, Bizarre', 'Weird, Reality, Complicated', 'Terrifying, Extreme, Confused', 'Thrills, Guessing, Intriguing', 'Gory, Disturbing, Guessing', 'Guessing, Creepy, Shock', 'Eating, Friendship, Ensemble', 'Tense, Guessing, Mysterious']
}, {
    'movie_title_formatted': 'glass-onion',
    'movie_title': 'Glass Onion',
    'type': 'movie',
    'year_released': 2022,
    'imdb_link': 'http://www.imdb.com/title/tt11564570/maindetails',
    'tmdb_link': 'https://www.themoviedb.org/movie/661374/',
    'imdb_id': 'tt11564570',
    'tmdb_id': '661374',
    'lb_rating': '3.5',
    'histogram': {
        '1.0': 6452,
        '2.0': 21998,
        '3.0': 16612,
        '4.0': 91915,
        '5.0': 96664,
        '6.0': 343027,
        '7.0': 320858,
        '8.0': 448228,
        '9.0': 122445,
        '10.0': 120663,
        'fans': 1500,
        'lb_rating': '3.5',
        'total': 1588862
    },
    'poster_url': 'https://a.ltrbxd.com/resized/film-poster/5/8/6/7/2/3/586723-glass-onion-a-knives-out-mystery-0-230-0-345-crop.jpg',
    'genres': ['Comedy', 'Crime', 'Mystery'],
    'production_countries': ['United States of America'],
    'spoken_languages': ['English'],
    'popularity': 84.356,
    'overview': 'World-famous detective Benoit Blanc heads to Greece to peel back the layers of a mystery surrounding a tech billionaire and his eclectic crew of friends.',
    'runtime': 140,
    'vote_average': 7.044,
    'vote_count': 5093,
    'release_date': '2022-11-12',
    'original_language': 'en',
    'themes': ['Thrillers and murder mysteries', 'Intriguing and suspenseful murder mysteries', 'Suspenseful crime thrillers'],
    'nanogenres': ['Murderer, Mysterious, Guessing', 'Killer, Crime, Suspects', 'Killer, Mysterious, Solving', 'Killing, Investigate, Twist', 'Humorous, Wit, Formulaic', 'Murderer, Clues, Convoluted', 'Delightful, Intelligent, Complicated', 'Victim, Investigate, Mysterious', 'Twist, Intriguing, Intrigue', 'Relationships, Mystery, Revelation']
}, {
    'movie_title_formatted': 'the-pale-blue-eye',
    'movie_title': 'The Pale Blue Eye',
    'type': 'movie',
    'year_released': 2022,
    'imdb_link': 'http://www.imdb.com/title/tt14138650/maindetails',
    'tmdb_link': 'https://www.themoviedb.org/movie/800815/',
    'imdb_id': 'tt14138650',
    'tmdb_id': '800815',
    'lb_rating': '3.1',
    'histogram': {
        '1.0': 523,
        '2.0': 1803,
        '3.0': 2647,
        '4.0': 12901,
        '5.0': 21118,
        '6.0': 46108,
        '7.0': 30395,
        '8.0': 19265,
        '9.0': 3331,
        '10.0': 4400,
        'fans': 131,
        'lb_rating': '3.1',
        'total': 142491
    },
    'poster_url': 'https://a.ltrbxd.com/resized/film-poster/7/1/8/2/4/1/718241-the-pale-blue-eye-0-230-0-345-crop.jpg',
    'genres': ['Thriller', 'Crime', 'Horror', 'Mystery'],
    'production_countries': ['United States of America'],
    'spoken_languages': ['English', 'Français', 'Latin'],
    'popularity': 25.209,
    'overview': 'West Point, New York, 1830. When a cadet at the burgeoning military academy is found hanged with his heart cut out, the top brass summons former New York City constable Augustus Landor to investigate. While attempting to solve this grisly mystery, the reluctant detective engages the help of one of the cadets: a strange but brilliant young fellow by the name of Edgar Allan Poe.',
    'runtime': 128,
    'vote_average': 6.847,
    'vote_count': 1678,
    'release_date': '2022-12-22',
    'original_language': 'en',
    'themes': ['Thrillers and murder mysteries', 'Intriguing and suspenseful murder mysteries', 'Suspenseful crime thrillers', 'Twisted dark psychological thriller', 'Noir and dark crime dramas', 'Terrifying, haunted, and supernatural horror'],
    'nanogenres': ['Killer, Detectives, Clues', 'Crime, Intriguing, Guilty', 'Tense, Mysterious, Solving', 'Spooky, Killer, Tense', 'Crime, Twist, Mysterious', 'Emotion, Complexity, Revelation', 'Suspense, Detective, Evidence', 'Death, Suspense, Dark', 'Investigate, Convoluted, Complicated', 'Murderer, Mysterious, Guessing']
}, {
    'movie_title_formatted': 'the-northman',
    'movie_title': 'The Northman',
    'type': 'movie',
    'year_released': 2022,
    'imdb_link': 'http://www.imdb.com/title/tt11138512/maindetails',
    'tmdb_link': 'https://www.themoviedb.org/movie/639933/',
    'imdb_id': 'tt11138512',
    'tmdb_id': '639933',
    'lb_rating': '3.8',
    'histogram': {
        '1.0': 2310,
        '2.0': 5719,
        '3.0': 4516,
        '4.0': 19343,
        '5.0': 23446,
        '6.0': 75877,
        '7.0': 107753,
        '8.0': 197241,
        '9.0': 88632,
        '10.0': 62085,
        'fans': 2500,
        'lb_rating': '3.8',
        'total': 586922
    },
    'poster_url': 'https://a.ltrbxd.com/resized/film-poster/5/6/5/8/5/2/565852-the-northman-0-230-0-345-crop.jpg',
    'genres': ['Action', 'Adventure', 'Fantasy'],
    'production_countries': ['China', 'United States of America'],
    'spoken_languages': ['English', 'Íslenska'],
    'popularity': 138.858,
    'overview': "Prince Amleth is on the verge of becoming a man when his father is brutally murdered by his uncle, who kidnaps the boy's mother. Two decades later, Amleth is now a Viking who's on a mission to save his mother, kill his uncle and avenge his father.",
    'runtime': 137,
    'vote_average': 7.066,
    'vote_count': 3986,
    'release_date': '2022-04-07',
    'original_language': 'en',
    'themes': ['Epic history and literature', 'Epic heroes', 'Humanity and the world around us', 'Fantasy adventure, heroism, and swordplay', 'Captivating vision and Shakespearean drama', 'Historical battles and epic heroism', 'Epic adventure and breathtaking battles', 'Bloody vampire horror'],
    'nanogenres': ['Hero, Evil, Complex', 'Fighting, Epic, Excitement', 'Swords, Mythology, Fantasy', 'Villain, Bloody, Battle', 'Voices, Battle, Action-Packed', 'Bloody, Action-Packed, Avenge', 'Death, Forest, Trip', 'Feelings, Complex, Captivating', 'Combat, Swords, Weapons', 'Myth, Imaginative, Quest']
}, {
    'movie_title_formatted': 'the-batman',
    'movie_title': 'The Batman',
    'type': 'movie',
    'year_released': 2022,
    'imdb_link': 'http://www.imdb.com/title/tt1877830/maindetails',
    'tmdb_link': 'https://www.themoviedb.org/movie/414906/',
    'imdb_id': 'tt1877830',
    'tmdb_id': '414906',
    'lb_rating': '4.0',
    'histogram': {
        '1.0': 4551,
        '2.0': 15085,
        '3.0': 8156,
        '4.0': 55963,
        '5.0': 47883,
        '6.0': 240936,
        '7.0': 255969,
        '8.0': 685555,
        '9.0': 359910,
        '10.0': 482992,
        'fans': 42000,
        'lb_rating': '4.0',
        'total': 2157000
    },
    'poster_url': 'https://a.ltrbxd.com/resized/film-poster/3/4/8/9/1/4/348914-the-batman-0-230-0-345-crop.jpg',
    'genres': ['Crime', 'Mystery', 'Thriller'],
    'production_countries': ['United States of America'],
    'spoken_languages': ['English'],
    'popularity': 184.755,
    'overview': 'In his second year of fighting crime, Batman uncovers corruption in Gotham City that connects to his own family while facing a serial killer known as the Riddler.',
    'runtime': 177,
    'vote_average': 7.685,
    'vote_count': 9462,
    'release_date': '2022-03-01',
    'original_language': 'en',
    'themes': ['Crime, drugs and gangsters', 'Epic heroes', 'High speed and special ops', 'Thrillers and murder mysteries', 'Superheroes in action-packed battles with villains', 'Explosive and action-packed heroes vs. villains', 'Violent action, guns, and crime', 'Noir and dark crime dramas', 'Intriguing and suspenseful murder mysteries'],
    'nanogenres': ['Comic-Book, Hero, Exciting', 'Fighting, Bullets, Exciting', 'Tense, Explosives, Bullets', 'Tense, Mysterious, Solving', 'Villain, Comic-Book, Campy', 'Hero, Evil, Complex', 'Villain, Stunts, Vengeance', 'Twist, Mysterious, Confusing', 'Criminal, Exciting, Climax', 'Explosives, Adventure, Predictable']
}];

const metrics = {
    'movies_reviewed': 60,
    'shows_reviewed': 0,
    'hours_watched': 8397.0,
    'most_common_countries': [{'country': "'United States of America'", 'count': 54}, {
        'country': "'United Kingdom'",
        'count': 17
    }, {'country': "'France'", 'count': 6}, {'country': "'Germany'", 'count': 3}, {
        'country': "'South Korea'",
        'count': 2
    }, {'country': "'Belgium'", 'count': 2}, {'country': "'China'", 'count': 2}, {
        'country': "'Canada'",
        'count': 2
    }, {'country': "'Japan'", 'count': 2}, {'country': "'Poland'", 'count': 2}, {
        'country': "'Czech Republic'",
        'count': 1
    }, {'country': "'Morocco'", 'count': 1}, {'country': "'Hong Kong'", 'count': 1}, {
        'country': "'Taiwan'",
        'count': 1
    }, {'country': "'Spain'", 'count': 1}],
    'mean_daily_reviews': 1.0,
    'number_daily_reviews_over_mean': 4,
    'logged_per_release_year': [{'year_released': 1962, 'num_movies': 1}, {
        'year_released': 1990,
        'num_movies': 1
    }, {'year_released': 1999, 'num_movies': 1}, {'year_released': 2001, 'num_movies': 1}, {
        'year_released': 2002,
        'num_movies': 2
    }, {'year_released': 2005, 'num_movies': 3}, {'year_released': 2006, 'num_movies': 3}, {
        'year_released': 2007,
        'num_movies': 2
    }, {'year_released': 2008, 'num_movies': 1}, {'year_released': 2010, 'num_movies': 2}, {
        'year_released': 2011,
        'num_movies': 1
    }, {'year_released': 2013, 'num_movies': 2}, {'year_released': 2014, 'num_movies': 4}, {
        'year_released': 2015,
        'num_movies': 3
    }, {'year_released': 2016, 'num_movies': 2}, {'year_released': 2017, 'num_movies': 1}, {
        'year_released': 2018,
        'num_movies': 2
    }, {'year_released': 2019, 'num_movies': 2}, {'year_released': 2021, 'num_movies': 3}, {
        'year_released': 2022,
        'num_movies': 8
    }, {'year_released': 2023, 'num_movies': 14}, {'year_released': 2024, 'num_movies': 2}],
    'logged_per_year': [{'year': '2022', 'num_reviews': 2}, {'year': '2023', 'num_reviews': 37}, {
        'year': '2024',
        'num_reviews': 22
    }],
    'average_rating_per_year': [{'year_released': 1962, 'average_rating': 8.0}, {
        'year_released': 1990,
        'average_rating': 8.0
    }, {'year_released': 1999, 'average_rating': 7.0}, {
        'year_released': 2001,
        'average_rating': 6.0
    }, {'year_released': 2002, 'average_rating': 7.5}, {
        'year_released': 2005,
        'average_rating': 6.333333333333333
    }, {'year_released': 2006, 'average_rating': 7.0}, {
        'year_released': 2007,
        'average_rating': 8.0
    }, {'year_released': 2008, 'average_rating': 4.0}, {
        'year_released': 2010,
        'average_rating': 8.5
    }, {'year_released': 2011, 'average_rating': 6.0}, {
        'year_released': 2013,
        'average_rating': 6.5
    }, {'year_released': 2014, 'average_rating': 5.75}, {
        'year_released': 2015,
        'average_rating': 7.0
    }, {'year_released': 2016, 'average_rating': 6.5}, {
        'year_released': 2017,
        'average_rating': 6.0
    }, {'year_released': 2018, 'average_rating': 6.5}, {
        'year_released': 2019,
        'average_rating': 6.0
    }, {'year_released': 2021, 'average_rating': 7.2}, {
        'year_released': 2022,
        'average_rating': 6.625
    }, {'year_released': 2023, 'average_rating': 6.4375}, {'year_released': 2024, 'average_rating': 8.5}],
    'longest_streak': 4,
    'average_rating_decade': [{'decade': 1960.0, 'average_rating': 8.0}, {
        'decade': 1990.0,
        'average_rating': 7.5
    }, {'decade': 2000.0, 'average_rating': 6.75}, {
        'decade': 2010.0,
        'average_rating': 6.526315789473684
    }, {'decade': 2020.0, 'average_rating': 6.848484848484849}],
    'top_10_movies_decade': [{
        'decade': 1960.0,
        'movie_title': 'The Manchurian Candidate',
        'year_released': 1962,
        'average_rating': 8.0
    }, {'decade': 1990.0, 'movie_title': 'GoodFellas', 'year_released': 1990, 'average_rating': 8.0}, {
        'decade': 1990.0,
        'movie_title': 'The Talented Mr. Ripley',
        'year_released': 1999,
        'average_rating': 7.0
    }, {'decade': 2000.0, 'movie_title': 'Zodiac', 'year_released': 2007, 'average_rating': 9.0}, {
        'decade': 2000.0,
        'movie_title': 'Kingdom of Heaven',
        'year_released': 2005,
        'average_rating': 8.0
    }, {
        'decade': 2000.0,
        'movie_title': 'Minority Report',
        'year_released': 2002,
        'average_rating': 8.0
    }, {
        'decade': 2000.0,
        'movie_title': 'American Gangster',
        'year_released': 2007,
        'average_rating': 7.0
    }, {
        'decade': 2000.0,
        'movie_title': 'Casino Royale',
        'year_released': 2006,
        'average_rating': 7.0
    }, {
        'decade': 2000.0,
        'movie_title': 'The Prestige',
        'year_released': 2006,
        'average_rating': 7.0
    }, {
        'decade': 2000.0,
        'movie_title': 'Mission: Impossible III',
        'year_released': 2006,
        'average_rating': 7.0
    }, {
        'decade': 2000.0,
        'movie_title': 'The Pianist',
        'year_released': 2002,
        'average_rating': 7.0
    }, {
        'decade': 2000.0,
        'movie_title': 'Training Day',
        'year_released': 2001,
        'average_rating': 6.0
    }, {
        'decade': 2000.0,
        'movie_title': 'Lord of War',
        'year_released': 2005,
        'average_rating': 6.0
    }, {
        'decade': 2010.0,
        'movie_title': 'The Social Network',
        'year_released': 2010,
        'average_rating': 9.0
    }, {
        'decade': 2010.0,
        'movie_title': 'The Big Short',
        'year_released': 2015,
        'average_rating': 8.0
    }, {'decade': 2010.0, 'movie_title': 'Godzilla', 'year_released': 2014, 'average_rating': 8.0}, {
        'decade': 2010.0,
        'movie_title': 'Inception',
        'year_released': 2010,
        'average_rating': 8.0
    }, {
        'decade': 2010.0,
        'movie_title': 'Snowpiercer',
        'year_released': 2013,
        'average_rating': 7.0
    }, {
        'decade': 2010.0,
        'movie_title': 'The Revenant',
        'year_released': 2015,
        'average_rating': 7.0
    }, {
        'decade': 2010.0,
        'movie_title': 'The Nice Guys',
        'year_released': 2016,
        'average_rating': 7.0
    }, {'decade': 2010.0, 'movie_title': 'Joker', 'year_released': 2019, 'average_rating': 7.0}, {
        'decade': 2010.0,
        'movie_title': 'Cold War',
        'year_released': 2018,
        'average_rating': 7.0
    }, {
        'decade': 2010.0,
        'movie_title': 'Interstellar',
        'year_released': 2014,
        'average_rating': 7.0
    }, {
        'decade': 2020.0,
        'movie_title': 'Mission: Impossible – Dead Reckoning Part One',
        'year_released': 2023,
        'average_rating': 9.0
    }, {'decade': 2020.0, 'movie_title': 'The Batman', 'year_released': 2022, 'average_rating': 9.0}, {
        'decade': 2020.0,
        'movie_title': 'Dune: Part Two',
        'year_released': 2024,
        'average_rating': 8.5
    }, {
        'decade': 2020.0,
        'movie_title': 'Anatomy of a Fall',
        'year_released': 2023,
        'average_rating': 8.0
    }, {'decade': 2020.0, 'movie_title': 'Past Lives', 'year_released': 2023, 'average_rating': 8.0}, {
        'decade': 2020.0,
        'movie_title': 'Oppenheimer',
        'year_released': 2023,
        'average_rating': 8.0
    }, {'decade': 2020.0, 'movie_title': 'Dune', 'year_released': 2021, 'average_rating': 7.5}, {
        'decade': 2020.0,
        'movie_title': 'TÁR',
        'year_released': 2022,
        'average_rating': 7.0
    }, {
        'decade': 2020.0,
        'movie_title': 'Glass Onion',
        'year_released': 2022,
        'average_rating': 7.0
    }, {
        'decade': 2020.0,
        'movie_title': 'The Northman',
        'year_released': 2022,
        'average_rating': 7.0
    }, {
        'decade': 2020.0,
        'movie_title': 'Killers of the Flower Moon',
        'year_released': 2023,
        'average_rating': 7.0
    }, {'decade': 2020.0, 'movie_title': 'The Pale Blue Eye', 'year_released': 2022, 'average_rating': 7.0}],
    'top_10_most_watched': [{'movie_title': 'dune-part-two', 'watch_count': 2}, {
        'movie_title': 'dune-2021',
        'watch_count': 2
    }, {'movie_title': 'oppenheimer-2023', 'watch_count': 2}, {
        'movie_title': 'mission-impossible-iii',
        'watch_count': 1
    }, {'movie_title': 'past-lives', 'watch_count': 1}, {
        'movie_title': 'anatomy-of-a-fall',
        'watch_count': 1
    }, {'movie_title': 'snowpiercer', 'watch_count': 1}, {
        'movie_title': 'the-iron-claw-2023',
        'watch_count': 1
    }, {'movie_title': 'inception', 'watch_count': 1}, {'movie_title': 'the-big-short', 'watch_count': 1}],
    'top_10_greater_than_average_rating': [{
        'movie_title': 'godzilla-2014',
        'rating_val': 8.0,
        'vote_average': 6.324,
        'margin': 1.6760000000000002
    }, {
        'movie_title': 'the-social-network',
        'rating_val': 9.0,
        'vote_average': 7.364,
        'margin': 1.6360000000000001
    }, {
        'movie_title': 'zodiac',
        'rating_val': 9.0,
        'vote_average': 7.521,
        'margin': 1.479
    }, {
        'movie_title': 'mission-impossible-dead-reckoning-part-one',
        'rating_val': 9.0,
        'vote_average': 7.55,
        'margin': 1.4500000000000002
    }, {
        'movie_title': 'the-batman',
        'rating_val': 9.0,
        'vote_average': 7.685,
        'margin': 1.3150000000000004
    }, {
        'movie_title': 'kingdom-of-heaven',
        'rating_val': 8.0,
        'vote_average': 6.939,
        'margin': 1.061
    }, {
        'movie_title': 'minority-report',
        'rating_val': 8.0,
        'vote_average': 7.3,
        'margin': 0.7000000000000002
    }, {
        'movie_title': 'dune-part-two',
        'rating_val': 9.0,
        'vote_average': 8.3,
        'margin': 0.6999999999999993
    }, {
        'movie_title': 'the-big-short',
        'rating_val': 8.0,
        'vote_average': 7.351,
        'margin': 0.649
    }, {'movie_title': 'the-manchurian-candidate', 'rating_val': 8.0, 'vote_average': 7.5, 'margin': 0.5}],
    'top_10_lower_than_average_rating': [{
        'movie_title': 'the-loft',
        'rating_val': 2.0,
        'vote_average': 6.4,
        'margin': -4.4
    }, {
        'movie_title': 'saltburn',
        'rating_val': 3.0,
        'vote_average': 7.067,
        'margin': -4.067
    }, {
        'movie_title': 'ferrari-2023',
        'rating_val': 3.0,
        'vote_average': 6.5,
        'margin': -3.5
    }, {
        'movie_title': 'the-menu-2022',
        'rating_val': 4.0,
        'vote_average': 7.192,
        'margin': -3.192
    }, {
        'movie_title': 'creed-iii',
        'rating_val': 4.0,
        'vote_average': 7.125,
        'margin': -3.125
    }, {
        'movie_title': 'quantum-of-solace',
        'rating_val': 4.0,
        'vote_average': 6.323,
        'margin': -2.3230000000000004
    }, {
        'movie_title': 'the-wind-rises',
        'rating_val': 6.0,
        'vote_average': 7.783,
        'margin': -1.7830000000000004
    }, {
        'movie_title': 'the-hateful-eight',
        'rating_val': 6.0,
        'vote_average': 7.751,
        'margin': -1.7510000000000003
    }, {
        'movie_title': 'godzilla-king-of-the-monsters-2019',
        'rating_val': 5.0,
        'vote_average': 6.694,
        'margin': -1.694
    }, {
        'movie_title': 'avatar-the-way-of-water',
        'rating_val': 6.0,
        'vote_average': 7.626,
        'margin': -1.6260000000000003
    }],
    'top_10_production_country_by_watch_count': [{
        'country': "'United States of America'",
        'count': 54
    }, {'country': "'United Kingdom'", 'count': 17}, {'country': "'France'", 'count': 6}, {
        'country': "'Germany'",
        'count': 3
    }, {'country': "'South Korea'", 'count': 2}, {'country': "'Belgium'", 'count': 2}, {
        'country': "'China'",
        'count': 2
    }, {'country': "'Canada'", 'count': 2}, {'country': "'Japan'", 'count': 2}, {'country': "'Poland'", 'count': 2}],
    'top_10_spoken_language_by_watch_count': [{'lang': "'English'", 'count': 57}, {
        'lang': "'Français'",
        'count': 19
    }, {'lang': "'Español'", 'count': 12}, {'lang': "'Italiano'", 'count': 10}, {
        'lang': "'Deutsch'",
        'count': 9
    }, {'lang': "'Pусский'", 'count': 7}, {'lang': "'日本語'", 'count': 5}, {
        'lang': "'普通话'",
        'count': 4
    }, {'lang': "'العربية'", 'count': 4}, {'lang': "'Latin'", 'count': 4}],
    'top_10_production_country_by_average_rating': [{
        'unnested_country': "'Spain'",
        'average_rating': 8.0
    }, {'unnested_country': "'South Korea'", 'average_rating': 7.5}, {
        'unnested_country': "'Germany'",
        'average_rating': 7.0
    }, {'unnested_country': "'Czech Republic'", 'average_rating': 7.0}, {
        'unnested_country': "'Taiwan'",
        'average_rating': 7.0
    }, {'unnested_country': "'Poland'", 'average_rating': 7.0}, {
        'unnested_country': "'Canada'",
        'average_rating': 7.0
    }, {'unnested_country': "'Hong Kong'", 'average_rating': 7.0}, {
        'unnested_country': "'United States of America'",
        'average_rating': 6.8
    }, {'unnested_country': "'United Kingdom'", 'average_rating': 6.526315789473684}],
    'top_10_spoken_countries_by_average_rating': [{
        'unnested_lang': "'Nederlands'",
        'average_rating': 8.0
    }, {'unnested_lang': "'svenska'", 'average_rating': 8.0}, {
        'unnested_lang': "'Kiswahili'",
        'average_rating': 8.0
    }, {'unnested_lang': "''", 'average_rating': 7.5}, {
        'unnested_lang': "'Íslenska'",
        'average_rating': 7.0
    }, {'unnested_lang': "'Český'", 'average_rating': 7.0}, {
        'unnested_lang': "'普通话'",
        'average_rating': 7.0
    }, {'unnested_lang': "'Hrvatski'", 'average_rating': 7.0}, {
        'unnested_lang': "'한국어/조선말'",
        'average_rating': 7.0
    }, {'unnested_lang': "'Latin'", 'average_rating': 7.0}],
    'top_10_genres_by_watch_count': [{
        'unnested_genre': "'Drama'",
        'watch_count': 23
    }, {'unnested_genre': " 'Adventure'", 'watch_count': 15}, {
        'unnested_genre': " 'Thriller'",
        'watch_count': 15
    }, {'unnested_genre': " 'Drama'", 'watch_count': 14}, {
        'unnested_genre': "'Science Fiction'",
        'watch_count': 11
    }, {'unnested_genre': " 'Crime'", 'watch_count': 11}, {
        'unnested_genre': " 'Action'",
        'watch_count': 10
    }, {'unnested_genre': "'Action'", 'watch_count': 9}, {
        'unnested_genre': " 'History'",
        'watch_count': 7
    }, {'unnested_genre': " 'Mystery'", 'watch_count': 7}],
    'top_10_themes_by_watch_count': [{
        'unnested_themes': " 'Superheroes in action-packed battles with villains'",
        'watch_count': 19
    }, {
        'unnested_themes': " 'Thought-provoking sci-fi action and future technology'",
        'watch_count': 15
    }, {
        'unnested_themes': " 'Humanity and the world around us'",
        'watch_count': 14
    }, {
        'unnested_themes': "'Epic heroes'",
        'watch_count': 14
    }, {
        'unnested_themes': " 'Emotional and captivating fantasy storytelling'",
        'watch_count': 12
    }, {
        'unnested_themes': " 'Twisted dark psychological thriller'",
        'watch_count': 12
    }, {
        'unnested_themes': " 'Explosive and action-packed heroes vs. villains'",
        'watch_count': 11
    }, {
        'unnested_themes': " 'Intense political and terrorist thrillers'",
        'watch_count': 10
    }, {
        'unnested_themes': " 'Intriguing and suspenseful murder mysteries'",
        'watch_count': 10
    }, {'unnested_themes': " 'Surreal and thought-provoking visions of life and death'", 'watch_count': 10}],
    'top_10_nanogenres_by_watch_count': [{
        'unnested_nanogenres': " 'Fighting",
        'watch_count': 28
    }, {'unnested_nanogenres': " 'Emotion", 'watch_count': 24}, {
        'unnested_nanogenres': " 'Action",
        'watch_count': 22
    }, {'unnested_nanogenres': ' Explosives', 'watch_count': 21}, {
        'unnested_nanogenres': " 'Suspense",
        'watch_count': 21
    }, {'unnested_nanogenres': " 'Drama", 'watch_count': 20}, {
        'unnested_nanogenres': " 'Tense",
        'watch_count': 19
    }, {'unnested_nanogenres': ' Thought-Provoking', 'watch_count': 16}, {
        'unnested_nanogenres': " Exciting'",
        'watch_count': 16
    }, {'unnested_nanogenres': " 'Relationships", 'watch_count': 15}],
    'top_10_genres_by_average_rating': [{
        'genre': " 'History'",
        'avg_rating': 7.571428571428571
    }, {'genre': " 'Mystery'", 'avg_rating': 7.571428571428571}, {
        'genre': "'Science Fiction'",
        'avg_rating': 7.545454545454546
    }, {'genre': " 'Adventure'", 'avg_rating': 7.466666666666667}, {
        'genre': "'Crime'",
        'avg_rating': 7.333333333333333
    }, {'genre': " 'Science Fiction'", 'avg_rating': 7.166666666666667}, {
        'genre': " 'War'",
        'avg_rating': 7.0
    }, {'genre': "'Action'", 'avg_rating': 7.0}, {'genre': "'Western'", 'avg_rating': 7.0}, {
        'genre': " 'Fantasy'",
        'avg_rating': 7.0
    }],
    'top_10_nanogenres_by_average_rating': [{'nanogenre': " 'Solving", 'avg_rating': 9.0}, {
        'nanogenre': " Unsettling'",
        'avg_rating': 9.0
    }, {'nanogenre': "'Geeks", 'avg_rating': 9.0}, {
        'nanogenre': " Obsession'",
        'avg_rating': 9.0
    }, {'nanogenre': ' Nerds', 'avg_rating': 9.0}, {
        'nanogenre': ' Girlfriend',
        'avg_rating': 9.0
    }, {'nanogenre': ' Cars', 'avg_rating': 9.0}, {
        'nanogenre': " 'Detectives",
        'avg_rating': 9.0
    }, {'nanogenre': ' Partner', 'avg_rating': 9.0}, {'nanogenre': ' Geeks', 'avg_rating': 9.0}],
    'top_10_themes_by_average_rating': [{
        'theme': " the undead and monster classics'",
        'avg_rating': 9.0
    }, {'theme': " 'Fascinating", 'avg_rating': 9.0}, {
        'theme': " emotional stories and documentaries'",
        'avg_rating': 9.0
    }, {'theme': " 'Horror", 'avg_rating': 9.0}, {
        'theme': " 'Teen school antics and laughter'",
        'avg_rating': 9.0
    }, {'theme': " 'Student coming-of-age challenges'", 'avg_rating': 9.0}, {
        'theme': " 'Sci-fi horror",
        'avg_rating': 8.0
    }, {'theme': ' creatures', 'avg_rating': 8.0}, {
        'theme': " and aliens'",
        'avg_rating': 8.0
    }, {'theme': " 'Faith and religion'", 'avg_rating': 8.0}],
    'average_watched_per_day_of_week': [{'day_of_week': 1, 'average_movies_watched': 1.0}, {
        'day_of_week': 2,
        'average_movies_watched': 1.0
    }, {'day_of_week': 3, 'average_movies_watched': 1.1428571428571428}, {
        'day_of_week': 4,
        'average_movies_watched': 1.0
    }, {'day_of_week': 5, 'average_movies_watched': 1.0714285714285714}, {
        'day_of_week': 6,
        'average_movies_watched': 1.0833333333333333
    }, {'day_of_week': 7, 'average_movies_watched': 1.1666666666666667}]
}

const ResultsPage = () => {
    const username: string = "theg0df4ther"
    const rec_title: string = username + "'s recommendations"
    const metrics_title: string = username + "'s statistics"
    return (
        <div>
            <Header/>
            <Tabs defaultValue="recs" className="w-full">
                <TabsList>
                    <TabsTrigger value="recs">Recommendations</TabsTrigger>
                    <TabsTrigger value="metrics">Statistics</TabsTrigger>
                </TabsList>
                <TabsContent value="recs">
                    <MovieGrid movies={movies} sectionTitle={rec_title}/>
                </TabsContent>
                <TabsContent value="metrics">
                    <Metrics data={metrics} sectionTitle={metrics_title}/>
                </TabsContent>
            </Tabs>
            <Footer/>
        </div>
    )
        ;
}

export default ResultsPage;