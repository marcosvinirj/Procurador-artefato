-- TrendPrint — schema minimo. Correr no SQL Editor do Supabase.
-- O score NAO e persistido: calcula-se na leitura a partir dos snapshots,
-- para recalibrar pesos sem migracao.

create table if not exists models (
  id               uuid primary key default gen_random_uuid(),
  name             text not null,
  category         text not null,
  keyword          text not null unique,          -- termo canonico de mercado
  synonyms         text[] not null default '{}',  -- variacoes, p/ nao subestimar o mercado
  status           text not null default 'active',-- active | pending | rejected | archived
  source           text,                          -- null = seed manual; senao, o conector que propos
  low_score_streak int not null default 0,        -- dias seguidos saturado; zera ao recuperar
  created_at       timestamptz not null default now()
);

-- Migracao: se a tabela ja existia (deploy anterior), acrescenta as colunas
-- que faltam. Idempotente — seguro correr este ficheiro inteiro outra vez.
alter table models add column if not exists status text not null default 'active';
alter table models add column if not exists source text;
alter table models add column if not exists low_score_streak int not null default 0;
create index if not exists models_status_idx on models (status);

create table if not exists snapshots (
  id              uuid primary key default gen_random_uuid(),
  model_id        uuid not null references models(id) on delete cascade,
  day             date not null,
  demand_raw      numeric,
  competition_raw numeric,
  margin_est      numeric,
  unique (model_id, day)
);

create index if not exists snapshots_model_day_idx on snapshots (model_id, day desc);
create index if not exists models_category_idx on models (category);

-- Seguranca: a API server-side usa a service key (que ignora RLS). Ligar RLS
-- sem qualquer policy deixa as chaves anon/publicadas sem acesso nenhum, mesmo
-- que uma delas escape para o browser.
alter table models    enable row level security;
alter table snapshots enable row level security;

insert into models (name, category, keyword, synonyms) values
  ('Polvo Articulado',            'brinquedos', 'articulated octopus',   '{"fidget octopus","flexi octopus","kraken toy"}'),
  ('Dragao Articulado',           'brinquedos', 'articulated dragon',    '{"flexi dragon","crystal dragon"}'),
  ('Axolote Flexi',               'brinquedos', 'flexi axolotl',         '{"articulated axolotl"}'),
  ('Cobra Articulada',            'brinquedos', 'articulated snake',     '{"flexi snake"}'),
  ('Fidget Slider',               'brinquedos', 'fidget slider',         '{"haptic slider","fidget toy 3d printed"}'),
  ('Cubo Infinito',               'brinquedos', 'infinity cube',         '{"fidget cube"}'),
  ('Tubarao Flexi',               'brinquedos', 'flexi shark',           '{"articulated shark"}'),
  ('Vaso Espiral',                'decoracao',  'spiral vase',           '{"twisted vase","vase mode vase"}'),
  ('Candeeiro Lua',               'decoracao',  'moon lamp',             '{"luna lamp","moon light"}'),
  ('Quadro Litofania',            'decoracao',  'lithophane',            '{"lithophane lamp","photo lithophane"}'),
  ('Vaso Rosto',                  'decoracao',  'face planter',          '{"head planter","face vase"}'),
  ('Painel Geometrico de Parede', 'decoracao',  'geometric wall art',    '{"3d wall panel","wall sculpture"}'),
  ('Presepio Minimalista',        'decoracao',  'nativity set',          '{"minimalist nativity"}'),
  ('Suporte de Auscultadores',    'utilidades', 'headphone stand',       '{"headset holder","headphone holder"}'),
  ('Organizador de Cabos',        'utilidades', 'cable organizer',       '{"cable clip","cord holder"}'),
  ('Suporte de Telemovel',        'utilidades', 'phone stand',           '{"phone holder","desk phone stand"}'),
  ('Caixa Modular Empilhavel',    'utilidades', 'stackable storage bin', '{"gridfinity bin","modular organizer"}'),
  ('Abridor de Frascos',          'utilidades', 'jar opener',            '{"grip jar opener"}'),
  ('Suporte de Papel Higienico',  'utilidades', 'toilet paper holder',   '{"tp holder"}'),
  ('Suporte de Chaves de Parede', 'utilidades', 'key holder wall',       '{"key hanger","entryway key rack"}'),
  ('Dock para Switch',            'gadgets',    'switch dock',           '{"nintendo switch stand","switch holder"}'),
  ('Suporte de Comando',          'gadgets',    'controller holder',     '{"controller stand","gamepad holder"}'),
  ('Suporte de Portatil',         'gadgets',    'laptop stand',          '{"notebook riser","laptop riser"}'),
  ('Organizador de Secretaria',   'gadgets',    'desk organizer',        '{"desk tray","desktop organizer"}'),
  ('Caixa para Auriculares',      'gadgets',    'earbud case',           '{"earbuds holder","airpods stand"}'),
  -- lote 2: pesquisado em 2026-09-13 (best-sellers reais de Etsy/MakerWorld/guias do setor)
  ('Torre de Dados',                     'brinquedos', 'dice tower',             '{"dnd dice tower","dice tower rpg","tabletop dice tower"}'),
  ('Cofre de Dados',                     'brinquedos', 'dice vault',             '{"dice storage box","polyhedral dice case"}'),
  ('Fidget Clicker',                     'brinquedos', 'fidget clicker',         '{"pop it fidget","clicker toy","fidget popper"}'),
  ('Busto Abstrato Geometrico',          'decoracao',  'abstract bust sculpture','{"modern face sculpture","geometric bust","abstract head sculpture"}'),
  ('Isolante de Lata',                   'decoracao',  'can cooler',             '{"beverage insulator","koozie 3d printed","drink can holder"}'),
  ('Vaso Geometrico',                    'decoracao',  'geometric planter',      '{"faceted plant pot","low poly planter","geometric plant pot"}'),
  ('Suporte de Celular para Carro',      'gadgets',    'car phone mount',        '{"phone holder car","vent phone mount","car dashboard phone holder"}'),
  ('Capa de Telemovel',                  'gadgets',    'phone case',             '{"custom phone case","printed phone cover","phone shell"}'),
  ('Tigela para Animais',                'utilidades', 'pet bowl',               '{"dog food bowl","elevated pet feeder","cat food bowl"}'),
  ('Coleira de Identificacao',           'utilidades', 'pet id tag',             '{"dog tag custom","cat name tag","pet name tag"}'),
  ('Clipe de Prateleira de Frigorifico', 'utilidades', 'fridge shelf clip',      '{"refrigerator shelf bracket","fridge replacement clip","shelf support clip"}'),
  ('Cortador de Biscoitos',              'utilidades', 'cookie cutter set',      '{"custom cookie cutter","3d printed cookie cutter","holiday cookie cutter"}')
on conflict (keyword) do nothing;

-- Contas (paywall). O catalogo continua partilhado por todos; aqui so vive
-- quem e cada utilizador e se pagou. is_paid NUNCA e escrito pelo cliente:
-- RLS ligado sem nenhuma politica — so a service key (servidor) le e escreve.
-- Se um utilizador pudesse editar o proprio perfil, marcava-se como pago.
create table if not exists profiles (
  id         uuid primary key references auth.users(id) on delete cascade,
  email      text,
  is_paid    boolean not null default false,
  created_at timestamptz not null default now()
);
alter table profiles enable row level security;

-- Administradores (painel /admin). Liga-se SO por SQL, nunca pelo site nem pela
-- API — assim ninguem se promove a admin. Depois de criares conta no site:
--   update public.profiles set is_admin = true where email = 'o-teu-email';
alter table profiles add column if not exists is_admin boolean not null default false;

-- Cria o perfil sozinho quando alguem se regista. security definer com
-- search_path vazio: corre com permissoes proprias sem poder ser sequestrado
-- por um objeto homonimo noutro schema.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id, email) values (new.id, new.email)
  on conflict (id) do nothing;
  return new;
end;
$$;
revoke execute on function public.handle_new_user() from public, anon, authenticated;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- Quem se registou antes deste trigger existir tambem ganha perfil (nao pago).
insert into public.profiles (id, email)
select id, email from auth.users
on conflict (id) do nothing;

-- Lote 3 (2026-09-21): nicho geek/nerd/anime/filmes. So acessorios genericos —
-- imprimir personagens com dono (Marvel, anime, jogos) e violacao de direito de
-- autor: o Etsy remove o anuncio e pode punir a conta.
insert into models (name, category, keyword, synonyms) values
  ('Bandeja de Dados',               'geek', 'dice tray',               '{"dnd dice tray","dice rolling tray"}'),
  ('Cenario de Mesa',                'geek', 'tabletop terrain',        '{"dnd terrain","wargame terrain","rpg terrain"}'),
  ('Estante de Miniaturas',          'geek', 'miniature display shelf', '{"miniature shelf","figure shelf"}'),
  ('Suporte para Pintar Miniaturas', 'geek', 'miniature painting handle','{"mini painting holder","hobby paint handle"}'),
  ('Book Nook',                      'geek', 'book nook',               '{"book nook shelf insert","bookshelf diorama"}'),
  ('Aparador de Livros',             'geek', 'manga bookend',           '{"comic bookend","book ends"}'),
  ('Caixa de Cartas',                'geek', 'deck box',                '{"tcg deck box","trading card case"}'),
  ('Suporte de Katana',              'geek', 'katana stand',            '{"sword stand","katana display"}'),
  ('Capacete de Cosplay',            'geek', 'cosplay helmet',          '{"cosplay prop","wearable helmet"}'),
  ('Suporte para Figuras',           'geek', 'figure display stand',    '{"figurine stand","figure holder"}'),
  ('Base de Luz LED',                'geek', 'led light base',          '{"acrylic light base","led display base"}'),
  ('Keycap Artesanal',               'geek', 'artisan keycap',          '{"custom keycap","keyboard keycap"}'),
  ('Estatua de Dragao',              'geek', 'fantasy dragon statue',   '{"dragon figurine","dragon sculpture"}'),
  ('Jogo de Xadrez',                 'geek', 'chess set',               '{"chess pieces","chess board set"}')
on conflict (keyword) do nothing;

-- Dados de RPG sao geek, nao brinquedo: o score compara dentro da categoria.
update models set category = 'geek' where keyword in ('dice tower', 'dice vault');

-- Lote 4 (2026-09-21): os bonecos em si, por FORMATO. Um chibi ou uma action
-- figure generica vende; o personagem com dono (Goku, Luffy, Marvel) e obra
-- derivada e sai do Etsy. A keyword mede o mercado; a arte tem de ser original.
insert into models (name, category, keyword, synonyms) values
  ('Boneco Chibi',            'geek', 'chibi figure',     '{"chibi figurine","chibi statue"}'),
  ('Figura de Anime',         'geek', 'anime figure',     '{"anime figurine","anime statue"}'),
  ('Boneco Articulado Poses', 'geek', 'action figure',    '{"poseable figure","articulated action figure"}'),
  ('Figura de Animal',        'geek', 'animal figurine',  '{"animal statue","cute animal figurine"}'),
  ('Miniatura de Secretaria', 'geek', 'desk figurine',    '{"desk decor figurine","office desk statue"}'),
  ('Decoracao Kawaii',        'geek', 'kawaii desk decor','{"cute desk decor","kawaii decor"}')
on conflict (keyword) do nothing;
