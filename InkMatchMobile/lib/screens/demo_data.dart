class DemoPost {
  const DemoPost({
    required this.id,
    required this.authorName,
    required this.authorRole,
    required this.city,
    required this.imagePath,
    required this.style,
    required this.tags,
    required this.description,
    required this.priceMin,
    required this.priceMax,
    required this.durationMinutes,
    required this.likes,
    required this.views,
    required this.comments,
    required this.createdAt,
  });

  final String id;
  final String authorName;
  final String authorRole;
  final String city;
  final String imagePath;
  final String style;
  final List<String> tags;
  final String description;
  final int priceMin;
  final int priceMax;
  final int durationMinutes;
  final int likes;
  final int views;
  final int comments;
  final String createdAt;
}

const demoPosts = <DemoPost>[
  DemoPost(
    id: 'p1',
    authorName: 'Viktor Ink',
    authorRole: 'Master',
    city: 'Saint Petersburg',
    imagePath: 'assets/styles/blackwork.jpg',
    style: 'Blackwork',
    tags: ['Gothic', 'Ornamental'],
    description: 'Dense blackwork forearm project with custom geometry.',
    priceMin: 7000,
    priceMax: 14000,
    durationMinutes: 180,
    likes: 241,
    views: 1290,
    comments: 34,
    createdAt: '2026-02-10 18:40',
  ),
  DemoPost(
    id: 'p2',
    authorName: 'Mira Needle',
    authorRole: 'Master',
    city: 'Moscow',
    imagePath: 'assets/styles/fineline.jpg',
    style: 'Fineline',
    tags: ['Mini', 'Flowers'],
    description: 'Fine line floral concept adapted to wrist anatomy.',
    priceMin: 4500,
    priceMax: 9000,
    durationMinutes: 120,
    likes: 187,
    views: 1022,
    comments: 19,
    createdAt: '2026-02-11 14:10',
  ),
  DemoPost(
    id: 'p3',
    authorName: 'Aki Trace',
    authorRole: 'Master',
    city: 'Kazan',
    imagePath: 'assets/styles/realism.jpg',
    style: 'Realism',
    tags: ['Animals', 'Nature'],
    description: 'Wolf realism portrait with smooth black-gray transitions.',
    priceMin: 12000,
    priceMax: 25000,
    durationMinutes: 300,
    likes: 315,
    views: 1810,
    comments: 51,
    createdAt: '2026-02-09 20:25',
  ),
  DemoPost(
    id: 'p4',
    authorName: 'Rin Mono',
    authorRole: 'Master',
    city: 'Yekaterinburg',
    imagePath: 'assets/tags/anime.jpg',
    style: 'Neo trad',
    tags: ['Anime', 'Cyberpunk'],
    description: 'Anime-inspired shoulder composition with neon details.',
    priceMin: 9000,
    priceMax: 16000,
    durationMinutes: 210,
    likes: 268,
    views: 1450,
    comments: 28,
    createdAt: '2026-02-12 09:30',
  ),
  DemoPost(
    id: 'p5',
    authorName: 'Daria Dot',
    authorRole: 'Master',
    city: 'Novosibirsk',
    imagePath: 'assets/styles/oldschool.jpg',
    style: 'Old school',
    tags: ['Lettering', 'Zodiac'],
    description: 'Classic old school flash with heavy lines and bright fill.',
    priceMin: 6000,
    priceMax: 13000,
    durationMinutes: 160,
    likes: 204,
    views: 990,
    comments: 17,
    createdAt: '2026-02-08 16:15',
  ),
  DemoPost(
    id: 'p6',
    authorName: 'Noah Grain',
    authorRole: 'Master',
    city: 'Moscow',
    imagePath: 'assets/tags/ornamental.jpg',
    style: 'Abstract',
    tags: ['Ornamental', 'Mini'],
    description: 'Abstract ornamental chest sketch with mirrored balance.',
    priceMin: 8000,
    priceMax: 17000,
    durationMinutes: 220,
    likes: 156,
    views: 860,
    comments: 12,
    createdAt: '2026-02-07 13:50',
  ),
];
