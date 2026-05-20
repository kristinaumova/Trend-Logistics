/** Метаданные по виду транспорта — не смешиваем с «всегда фура». */
export const TRANSPORT_META = {
  truck: {
    short: 'Авто',
    title: 'Автомобильная перевозка',
    subtitle: 'Фура / сборный груз по автодорогам',
    icon: '🚛',
  },
  rail: {
    short: 'Ж/д',
    title: 'Железнодорожная перевозка',
    subtitle: 'Вагоны и контейнерные поезда',
    icon: '🚆',
  },
  sea: {
    short: 'Море',
    title: 'Морская / речная перевозка',
    subtitle: 'Контейнерные линии, речной лег',
    icon: '🚢',
  },
  air: {
    short: 'Авиа',
    title: 'Авиаперевозка',
    subtitle: 'Грузовые авиарейсы, хабы',
    icon: '✈️',
  },
}

export function getTransportMeta(type) {
  return TRANSPORT_META[type] || TRANSPORT_META.truck
}
