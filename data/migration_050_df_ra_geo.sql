-- Migration 050: Coordenadas geográficas das 35 Regiões Administrativas do DF
-- Adiciona latitude/longitude dos centroides para gráficos Mapbox

BEGIN;

ALTER TABLE df_regioes_administrativas
ADD COLUMN IF NOT EXISTS latitude NUMERIC(9,6),
ADD COLUMN IF NOT EXISTS longitude NUMERIC(9,6);

-- Centroides das 35 RAs (fonte: GDF/Mapas de Brasília)
UPDATE df_regioes_administrativas SET latitude = -15.7801, longitude = -47.9292 WHERE ra_codigo = '5300108'; -- Plano Piloto
UPDATE df_regioes_administrativas SET latitude = -15.8389, longitude = -48.0278 WHERE ra_codigo = '5300207'; -- Águas Claras
UPDATE df_regioes_administrativas SET latitude = -15.8175, longitude = -48.0611 WHERE ra_codigo = '5300306'; -- Taguatinga
UPDATE df_regioes_administrativas SET latitude = -15.8133, longitude = -48.1128 WHERE ra_codigo = '5300405'; -- Ceilândia
UPDATE df_regioes_administrativas SET latitude = -15.8803, longitude = -48.0853 WHERE ra_codigo = '5300504'; -- Samambaia
UPDATE df_regioes_administrativas SET latitude = -16.0167, longitude = -48.0000 WHERE ra_codigo = '5300603'; -- Santa Maria
UPDATE df_regioes_administrativas SET latitude = -15.6500, longitude = -47.7917 WHERE ra_codigo = '5300702'; -- Sobradinho
UPDATE df_regioes_administrativas SET latitude = -15.6206, longitude = -47.6483 WHERE ra_codigo = '5300801'; -- Planaltina
UPDATE df_regioes_administrativas SET latitude = -15.7333, longitude = -47.7833 WHERE ra_codigo = '5300900'; -- Paranoá
UPDATE df_regioes_administrativas SET latitude = -15.8667, longitude = -47.9667 WHERE ra_codigo = '5301007'; -- Núcleo Bandeirante
UPDATE df_regioes_administrativas SET latitude = -15.9589, longitude = -48.0553 WHERE ra_codigo = '5301106'; -- Gama
UPDATE df_regioes_administrativas SET latitude = -15.8300, longitude = -47.9780 WHERE ra_codigo = '5301205'; -- Guará
UPDATE df_regioes_administrativas SET latitude = -15.7939, longitude = -47.9828 WHERE ra_codigo = '5301304'; -- Cruzeiro
UPDATE df_regioes_administrativas SET latitude = -15.8000, longitude = -47.9500 WHERE ra_codigo = '5301403'; -- Sudoeste/Octogonal
UPDATE df_regioes_administrativas SET latitude = -15.8167, longitude = -48.0333 WHERE ra_codigo = '5301502'; -- Candangolândia
UPDATE df_regioes_administrativas SET latitude = -15.9167, longitude = -48.0600 WHERE ra_codigo = '5301601'; -- Recanto das Emas
UPDATE df_regioes_administrativas SET latitude = -15.7350, longitude = -47.8500 WHERE ra_codigo = '5301700'; -- Lago Norte
UPDATE df_regioes_administrativas SET latitude = -15.8050, longitude = -47.8700 WHERE ra_codigo = '5301809'; -- Lago Sul
UPDATE df_regioes_administrativas SET latitude = -15.8833, longitude = -48.0167 WHERE ra_codigo = '5301908'; -- Riacho Fundo
UPDATE df_regioes_administrativas SET latitude = -15.6700, longitude = -47.7900 WHERE ra_codigo = '5302005'; -- Sobradinho II
UPDATE df_regioes_administrativas SET latitude = -15.8500, longitude = -47.9500 WHERE ra_codigo = '5302104'; -- Park Way
UPDATE df_regioes_administrativas SET latitude = -15.9011, longitude = -47.7678 WHERE ra_codigo = '5302203'; -- São Sebastião
UPDATE df_regioes_administrativas SET latitude = -15.7833, longitude = -48.0000 WHERE ra_codigo = '5302302'; -- Vicente Pires
UPDATE df_regioes_administrativas SET latitude = -15.6400, longitude = -47.8000 WHERE ra_codigo = '5302401'; -- Sobradinho I
UPDATE df_regioes_administrativas SET latitude = -15.7333, longitude = -47.7500 WHERE ra_codigo = '5302500'; -- Itapoã
UPDATE df_regioes_administrativas SET latitude = -15.8833, longitude = -48.1167 WHERE ra_codigo = '5302609'; -- Sol Nascente/Pôr do Sol
UPDATE df_regioes_administrativas SET latitude = -15.7000, longitude = -47.8200 WHERE ra_codigo = '5302708'; -- Ponte Alta
UPDATE df_regioes_administrativas SET latitude = -15.6500, longitude = -47.8500 WHERE ra_codigo = '5302807'; -- Arapoanga
UPDATE df_regioes_administrativas SET latitude = -15.9333, longitude = -48.0500 WHERE ra_codigo = '5302906'; -- Águas Lindas de Goiás
UPDATE df_regioes_administrativas SET latitude = -15.6200, longitude = -47.8200 WHERE ra_codigo = '5303003'; -- Fercal
UPDATE df_regioes_administrativas SET latitude = -15.9333, longitude = -48.0333 WHERE ra_codigo = '5303102'; -- Novo Gama
UPDATE df_regioes_administrativas SET latitude = -15.8667, longitude = -47.9333 WHERE ra_codigo = '5303201'; -- Jardim Botânico
UPDATE df_regioes_administrativas SET latitude = -15.8167, longitude = -48.0100 WHERE ra_codigo = '5303300'; -- Iguatemi
UPDATE df_regioes_administrativas SET latitude = -15.8100, longitude = -48.0200 WHERE ra_codigo = '5303409'; -- Miguel Couto
UPDATE df_regioes_administrativas SET latitude = -15.7900, longitude = -47.9600 WHERE ra_codigo = '5303508'; -- Setor de Industrias

CREATE INDEX IF NOT EXISTS idx_ra_coords ON df_regioes_administrativas (latitude, longitude);

COMMIT;
