-- TrendPrint — schema minimo. Correr no SQL Editor do Supabase.
-- O score NAO e persistido: calcula-se na leitura a partir dos snapshots,
-- para recalibrar pesos sem migracao.

create table if not exists models (
  id         uuid primary key default gen_random_uuid(),
  name       text not null,
  category   text not null,
  keyword    text not null unique,          -- termo canonico de mercado
  synonyms   text[] not null default '{}',  -- variacoes, p/ nao subestimar o mercado
  created_at timestamptz not null default now()
);

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
  ('Caixa para Auriculares',      'gadgets',    'earbud case',           '{"earbuds holder","airpods stand"}')
on conflict (keyword) do nothing;
